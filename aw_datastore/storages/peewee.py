from decimal import Decimal
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
import re
import ctypes
from urllib.parse import unquote

import pytz
import tldextract
from playhouse.shortcuts import model_to_dict

from aw_core.cache import cache_user_credentials
from aw_core import db_cache
from aw_core.launch_start import create_shortcut, launch_app, check_startup_status
from aw_qt.manager import Manager

if sys.platform == "win32":
    _module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
    os.add_dll_directory(_module_dir)
elif sys.platform == "darwin":
    _module_dir = os.path.dirname(os.path.realpath(__file__))
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(os.path.join(_module_dir, os.pardir))))
    libsqlcipher_path = _parent_dir
    openssl = ctypes.cdll.LoadLibrary(libsqlcipher_path + '/libcrypto.3.dylib')
    libsqlcipher = ctypes.cdll.LoadLibrary(libsqlcipher_path + '/libsqlcipher.0.dylib')

from aw_core.util import decrypt_uuid, get_document_title, get_domain, load_key, remove_more_page_suffix, \
    start_all_module, stop_all_module
import keyring
import iso8601
from aw_core.dirs import get_data_dir
from aw_core.models import Event
from playhouse.migrate import SqliteMigrator, migrate
from playhouse.sqlcipher_ext import SqlCipherDatabase

import peewee
from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    DecimalField,
    BooleanField,
    TextField,
    ForeignKeyField,
    IntegerField,
    Model,
    DatabaseProxy,
)

from .abstract import AbstractStorage
from cryptography.fernet import Fernet
import cryptocode
import keyring
from peewee import DoesNotExist

logging.basicConfig(encoding='utf-8')

logger = logging.getLogger(__name__)

# Prevent debug output from propagating
peewee_logger = logging.getLogger("peewee")
peewee_logger.setLevel(logging.INFO)

# Init'd later in the PeeweeStorage constructor.
#   See: http://docs.peewee-orm.com/en/latest/peewee/database.html#run-time-database-configuration
# Another option would be to use peewee's Proxy.
#   See: http://docs.peewee-orm.com/en/latest/peewee/database.html#dynamic-db
db_proxy = DatabaseProxy()
_db = None

LATEST_VERSION = 2
application_cache_key = "application_cache"
settings_cache_key = "settings_cache"


def auto_migrate(db: Any, path: str) -> None:
    """
     Migrate bucketmodel to latest version. This is a wrapper around : func : ` ~sqlalchemy. orm. migrate ` to allow a user to specify a path to the database and to use it as a context manager.

     @param db - The database to migrate. It must be a
     @param path - The path to the database.

     @return None if no errors otherwise an error object with the errors
    """
    db.init(path)
    db.connect()
    migrator = SqliteMigrator(db)

    # check if bucketmodel has datastr field
    info = db.execute_sql("PRAGMA table_info(bucketmodel)")
    has_datastr = any(row[1] == "datastr" for row in info)

    # Add the datastr column to the bucketmodel.
    if not has_datastr:
        datastr_field = CharField(default="{}")
        with db.atomic():
            migrate(migrator.add_column("bucketmodel", "datastr", datastr_field))

    info = db.execute_sql("PRAGMA table_info(eventmodel)")
    has_server_sync_status = any(row[1] == "server_sync_status" for row in info)

    # Add the server_sync_status_field column to the eventmodel.
    if not has_server_sync_status:
        server_sync_status_field = IntegerField(default=0)
        with db.atomic():
            migrate(migrator.add_column("eventmodel", "server_sync_status", server_sync_status_field))

    db.close()


def chunks(ls, n):
    """
     Yield successive n - sized chunks from a list. This is useful for debugging and to ensure that chunks don't get stuck in memory at the cost of memory usage.

     @param ls - List to split into chunks. Must be an instance of
     @param n - Number of chunks to
    """
    # Generator that yields all n elements of ls
    for i in range(0, len(ls), n):
        yield ls[i: i + n]


def dt_plus_duration(dt, duration):
    """
     Add duration to a datetime. This is useful for displaying time stamps.

     @param dt - datetime to add duration to. If it's a date we'll use it as the start of the time stamp.
     @param duration - duration to add to the datetime. If it's a number we'll add it to the end of the time stamp.

     @return string with date and duration in YYYY - MM - DD HH : MM : SS
    """
    # See peewee docs on datemath: https://docs.peewee-orm.com/en/latest/peewee/hacks.html#date-math
    return peewee.fn.strftime(
        "%Y-%m-%d %H:%M:%f+00:00",
        (peewee.fn.julianday(dt) - 2440587.5) * 86400.0 + duration,
        "unixepoch",
    )



class BaseModel(Model):
    class Meta:
        database = db_proxy


class BucketModel(BaseModel):
    key = IntegerField(primary_key=True)
    id = CharField(unique=True)
    created = DateTimeField(default=datetime.now)
    name = CharField(null=True)
    type = CharField()
    client = CharField()
    hostname = CharField()
    datastr = CharField(null=True)  # JSON-encoded object

    def json(self):
        """
         Convert to JSON for sending to API. This is used to create a request to the API.


         @return The JSON representation of the object as a dictionary. Note that the dictionary will be empty if there is no data
        """
        return {
            "id": self.id,
            "created": iso8601.parse_date(self.created)
            .astimezone(timezone.utc)
            .isoformat(),
            "name": self.name,
            "type": self.type,
            "client": self.client,
            "hostname": self.hostname,
            "data": json.loads(self.datastr) if self.datastr else {},
        }

class ApplicationModel(BaseModel):
    id = AutoField()
    type = CharField()
    name = CharField(null=True, unique=True)
    url = CharField(null=True, unique=True)
    alias = CharField(null=True)
    is_blocked = BooleanField(default=0)
    is_ignore_idle_time = BooleanField(default=0)
    color = CharField(null=True)
    created_at = DateTimeField(default=datetime.now())
    updated_at = DateTimeField(default=datetime.now())
    criteria = CharField(null=True)

    @classmethod
    def from_application_details(cls, application_details):
        logger.info(f"Processing application details: {application_details}")

        # Early return for AFK app_name
        if application_details.get('app_name', '').lower() == 'afk':
            logger.info("AFK event detected, returning None")
            return None

        # Extract application details
        app_url = application_details.get("url", None)
        if app_url is not None:
            app_url = app_url.strip()

        app_name = application_details.get("app_name", None)
        if app_name is not None:
            app_name = app_name.replace('.exe', '').strip()

        try:
            new_instance, created = cls.get_or_create(
                type="web application" if app_url else "application",
                name=app_name if not app_url else None,
                url=app_url if app_url else None,
                alias=application_details.get("alias", ""),
                is_blocked=application_details.get("is_blocked", False),
                is_ignore_idle_time=application_details.get("idle_time_ignored", False),
                color=application_details.get("color", ""),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                criteria=application_details.get("criteria", "")
            )

            if created:
                logger.info(f"New application created: {new_instance}")
            else:
                logger.info(f"Application already exists: {new_instance}")

            return new_instance

        except peewee.IntegrityError as e:
            # logger.warning(f"Integrity error occurred: {e}")
            # Here you handle the violation gracefully
            # Check all fields for an existing record
            existing_instance = cls.get_or_none(
                type="web application" if app_url else "application",
                name=app_name if not app_url else None,
                url=app_url if app_url else None,
                alias=application_details.get("alias", ""),
                is_blocked=application_details.get("is_blocked", False),
                is_ignore_idle_time=application_details.get("idle_time_ignored", False),
                color=application_details.get("color", ""),
                criteria=application_details.get("criteria", "")
            )
            if existing_instance:
                logger.info(f"Updating existing application: {existing_instance}")
                # Update the existing instance with new values
                existing_instance.alias = application_details.get("alias", "")
                existing_instance.is_blocked = application_details.get("is_blocked", False)
                existing_instance.is_ignore_idle_time = application_details.get("idle_time_ignored", False)
                existing_instance.color = application_details.get("color", "")
                existing_instance.criteria = application_details.get("criteria", "")
                existing_instance.save()
                logger.info(f"Existing application updated: {existing_instance}")
                return existing_instance
            else:
                logger.error("No existing application found to update")
                # You can choose to raise the error or handle it differently based on your application's needs

    def json(self):
        """
        Convert the model instance to a JSON-compatible dictionary.
        :return: A dictionary representation of the settings.
        """
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "url": self.url,
            "alias": self.alias,
            "is_blocked": self.is_blocked,
            "is_ignore_idle_time": self.is_ignore_idle_time,
            "color": self.color,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S'),  # Convert to a string in the desired format
            "updated_at": self.updated_at.strftime('%Y-%m-%d %H:%M:%S'),  # Convert to a string in the desired format
            "criteria": self.criteria
        }

def blocked_apps(ap_name):
    """
    blocking app
    """
    blocked_apps = ApplicationModel.select().where(ApplicationModel.is_blocked==1)
    # print('blockeda apps',blocked_apps)

    apps_info=[{'id':apps.id,'name':apps.name,'is_blocked':apps.is_blocked,'url':apps.url} for apps in list(blocked_apps)]
    block_list=[key['name'] for key in apps_info]
    if ap_name in block_list:
        return True
    else:
        return False
def blocked_url(url):
    """
    blocking url
    """
    blocked_apps = ApplicationModel.select().where(ApplicationModel.is_blocked == True)

    # Fetch the results from the queryset and convert them to a list
    blocked_apps_list = list(blocked_apps)

    # Extract URLs from blocked apps and create a list of substrings
    block_list_url = [app.url.strip().split('//')[1] for app in blocked_apps_list if app.url]
    if url:
        url = url.strip()  # Remove leading and trailing whitespace from the input URL
        for blocked_url in block_list_url:
            if blocked_url.lower() == url.lower():  # Perform case-insensitive comparison
                return True

    return False




class EventModel(BaseModel):
    id = AutoField()
    bucket = ForeignKeyField(BucketModel, backref="events", index=True)
    timestamp = DateTimeField(index=True, default=datetime.now)
    duration = DecimalField()
    datastr = CharField()
    app = CharField()
    title = TextField(null=True)
    url = TextField(null=True)
    application_name = CharField(max_length=50)
    server_sync_status = IntegerField(default=0)

    @classmethod
    def from_event(cls, bucket_key, event: Event):
        """
        Create an EventModel instance from a Cloud Pub/Sub event.

        @param cls - The class to use for the new event.
        @param bucket_key - The key of the bucket to use for the new event.
        @param event - The event to create the event from. Must have a non-empty Event attribute.

        @return The newly created EventModel instance or None if conditions are not met
        """
        if cls is not None:
            # logger.info("Creating EventModel from event: %s", event)

            app_name = None
            title_name = event.data.get('title')
            application_name = event.data.get('app')
            if not event.data.get('url'):
                app_name = event.data.get('app', '')
                if ".exe" in app_name.lower():
                    app_name = re.sub(r'\.exe$', '', app_name)
            else:
                url = event.data.get('url', '')
                app_name = get_domain(url)
                if "sharepoint.com" in url:
                    app_name = "OneDrive"

            if ".exe" in app_name.lower():
                app_name = re.sub(r'\.exe$', '', app_name)
            if "ApplicationFrameHost" in app_name or "Code" in app_name:
                titles = re.split(r'\s-\s|\s\|\s', event.title)
                if titles and isinstance(titles, list):
                    app_name = titles[-2] if len(titles) > 1 else titles[-1]
            if "explorer" in app_name:
                app_name = event.title
            if "localhost" in app_name or "10" in app_name or "14" in app_name:
                titles = re.split(r'\s—\s|\s-\s|\s\|\s', event.title)
                if titles and isinstance(titles, list):
                    app_name = remove_more_page_suffix(titles[0])
            # logger.info("Title: %s, Application: %s", title_name, application_name)

                # dct['id']=apps.id
                # dct['type']=apps.type
                # dct['name']=apps.name
            #     dct['url']=apps.url
            #     dct['alias']=apps.alias
            #     dct['is_blocked']=apps.is_blocked
            #     dct['is_ignore_idle_time']=apps.is_ignore_idle_time
            ApplicationModel.from_application_details(
                {"app_name": event.data.get('app', ''), "url": event.data.get('url', '')})
            ap_name=application_name.split('.')[0]
            url_link=event.data.get('url')
            # blocked=blocked_apps(ap_name,url_link)
            if application_name != '' and title_name != '':
                try:
                    event_model = cls(
                        bucket=bucket_key,
                        id=event.id,
                        timestamp=event.timestamp,
                        duration=event.duration.total_seconds(),
                        datastr=json.dumps(event.data),
                        app=event.data.get('app', ''),
                        title=title_name,
                        url=event.data.get('url', ''),
                        application_name=app_name,
                        server_sync_status=cls.server_sync_status or 0
                    )
                    # decoded_title = bytes(event_model.title, 'utf-8').decode('unicode_escape')
                    # # Log the decoded title
                    # logging.info("EventModel %s", decoded_title.decoded('utf-8'))
                    # logger.info("EventModel %s", title_name.encode('utf-8'))
                    return event_model
                except ValueError as ve:
                    logger.warning("Vallue Error raised events not inserted: %s", str(ve))
                    return None  # Return None explicitly in case of an exception
                except AttributeError as ae:
                    logger.warning("AttributeError: %s", str(ae))
                    return None
            else:
                return None  # Return None if conditions are not met
        else:
            logger.warning("cls object is none")

        return cls(
            bucket=bucket_key,
            id=event.id,
            timestamp=event.timestamp,
            duration=event.duration.total_seconds(),
            datastr=json.dumps(event.data),
            app=event.data.get('app', ''),
            title=event.data.get('title', ''),
            url=event.data.get('url', ''),
            application_name=app_name,
            server_sync_status=0
        )

    def json(self):
        """
        Convert to JSON for use in json.dumps. This is useful for debugging and to avoid having to re-serialize every time the object is serialized.

        @return A dict with the data that can be serialized
        """
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "duration": float(self.duration),
            "data": json.loads(self.datastr),
            "app": self.app,
            "title": self.title,
            "url": self.url,
            "application_name": self.application_name,
            "server_sync_status": self.server_sync_status
        }


class SettingsModel(BaseModel):
    id = AutoField()
    code = CharField(unique=True)  # Ensure 'code' is unique across all settings
    value = TextField()

    def json(self):
        """
        Convert the settings value from a JSON string to a Python dictionary for easier access in the application.
        """
        return {
            "id": self.id,
            "code": self.code,
            "value": json.loads(self.value),  # Assuming the value is stored in JSON format
        }

    @classmethod
    def from_settings(cls, code, value):
        """
        Helper method to create a SettingsModel instance from a code and a Python dictionary value.
        This method serializes the value to a JSON string for storage.
        """
        return cls(
            code=code,
            value=json.dumps(value),  # Serialize the Python dictionary to a JSON string
        )


def format_timezone_offset(offset):
    """
    Formats the timezone offset into the format "-08:00".
    :param offset: The timezone offset to format.
    :return: The formatted timezone offset.
    """
    # Extract hours and minutes from the offset
    hours = offset[:3]
    minutes = offset[3:]

    # Add the colon between hours and minutes
    formatted_offset = f"{hours}:{minutes}"
    return formatted_offset


def setup_weekday_settings():
    try:
        # Define default settings for weekdays
        default_weekday_settings = {
            "Monday": False,
            "Tuesday": False,
            "Wednesday": False,
            "Thursday": False,
            "Friday": False,
            "Saturday": False,
            "Sunday": False,
            "starttime": "9:30 AM",
            "endtime": "6:30 PM"
        }

        # Check if the weekday settings already exist in the database
        existing_weekday_instance = SettingsModel.get_or_none(code="weekdays_schedule")
        if not existing_weekday_instance:
            SettingsModel.from_settings(code="weekdays_schedule", value=default_weekday_settings).save()
            print("Weekday schedule settings added successfully.")

    except Exception as e:
        print(f"An unexpected error occurred while setting up weekday settings: {e}")


def ensure_default_settings():
    # Use strftime with %z to format the timezone as +HHMM
    # Then insert a colon to get the +HH:MM format
    tz_offset = datetime.now(timezone.utc).astimezone().strftime('%z')
    formatted_tz = tz_offset[:3] + ':' + tz_offset[3:]  # Format to +HH:MM

    default_settings = {
        "time_zone": formatted_tz,
        "timeformat": 12,
        "schedule": False,
        "launch": True
    }

    for code, value in default_settings.items():
        setting, created = SettingsModel.get_or_create(code=code, defaults={"value": json.dumps(value)})
        if created:
            print(f"Created default setting: {code} = {value}")
        else:
            print(f"Default setting already exists: {code} = {setting.value}")



class PeeweeStorage(AbstractStorage):
    sid = "peewee"

    def __init__(self, testing: bool = True, filepath: Optional[str] = None) -> None:
        """
         Initialize the database. This is called by __init__ and should not be called directly

         @param testing - If True will be used for testing
         @param filepath - Path to the database file ( default : None )

         @return True if initialization was successful False if there was an
        """
        self.init_db()

    def init_db(self, testing: bool = True, filepath: Optional[str] = None) -> bool:
        """
         Initialize or re - initialize the database. This is called by : py : meth : ` connect ` and

         @param testing - If True use test data instead of production
         @param filepath - Path to the database file

         @return True if the database was initialized False if it was
        """
        db_key = ""
        cache_key = "TTim"
        cached_credentials = cache_user_credentials(cache_key, "SD_KEYS")
        database_changed = False  # Flag to track if the database has been changed

        # Returns the encrypted db_key if the cached credentials are cached.
        if cached_credentials is not None:
            db_key = cached_credentials.get("encrypted_db_key")
        else:
            db_key = None

        key = load_key('user_key')

        # This method will create a new database and migrate it if necessary.
        if db_key is None or key is None:
            logger.info("User account not exist")
            data_dir = get_data_dir("aw-server")

            # If not filepath is not set create a new file in data_dir.
            if not filepath:
                filename = (
                        "peewee-sqlite"
                        + ("-testing" if testing else "")
                        + f".v{LATEST_VERSION}"
                        + ".db"
                )
                filepath = os.path.join(data_dir, filename)

            try:
                os.remove(filepath)
                database_changed = True
            except Exception:
                pass

            return False
        else:
            password = decrypt_uuid(db_key, key)
            user_email = cached_credentials.get("email")
            # Return true if password is not password
            if not password:
                return False

            data_dir = get_data_dir("aw-server")

            # Check if the database file is changed.
            if not filepath:
                filename = (
                        "peewee-sqlite"
                        + f"-{user_email}"
                        + f".v{LATEST_VERSION}"
                        + ".db"
                )
                filepath = os.path.join(data_dir, filename)
            else:
                # Check if the database file path has changed
                # If the file is not the same as the data directory as the data directory.
                if filepath != os.path.join(data_dir, filename):
                    database_changed = True
            _db = SqlCipherDatabase(None, passphrase=password)
            print("passowrd",password)
            db_proxy.initialize(_db)
            self.db = _db
            self.db.init(filepath)
            logger.info(f"Using database file: {filepath}")
            self.db.connect()

            try:
                BucketModel.create_table(safe=True)
                EventModel.create_table(safe=True)
                SettingsModel.create_table(safe=True)
                ApplicationModel.create_table(safe=True)
                database_changed = True  # Assume tables creation is a change
            except Exception:
                pass  # If tables already exist, it's not a change

            # Migrate database if needed, requires closing the connection first
            self.db.close()
            # If auto_migrate is called automatically if auto_migrate is called.
            if auto_migrate(_db, filepath):  # Assuming auto_migrate returns True if migration happens
                database_changed = True
            self.db.connect()

            # Update bucket keys
            self.update_bucket_keys()

            ensure_default_settings()
            setup_weekday_settings()
            db_cache.store(application_cache_key, self.retrieve_application_names())
            db_cache.store(settings_cache_key, self.retrieve_all_settings())
            self.save_settings("launch", check_startup_status())
            # Stop all modules that have been changed.
            if database_changed:
                stop_all_module()
            start_all_module()
            self.launch_application_start()
            return True

    def update_bucket_keys(self) -> None:
        """
         Update the bucket keys. This is called after the user has selected a bucket to update it's key and bucket_id


         @return None but raises an exception if there is no
        """
        buckets = BucketModel.select()
        self.bucket_keys = {bucket.id: bucket.key for bucket in buckets}

    def buckets(self) -> Dict[str, Dict[str, Any]]:
        """
         Get all buckets. This is a dictionary of bucket IDs to JSON objects.


         @return A dictionary of bucket IDs to JSON objects keyed by bucket
        """
        return {bucket.id: bucket.json() for bucket in BucketModel.select()}

    def create_bucket(
            self,
            bucket_id: str,
            type_id: str,
            client: str,
            hostname: str,
            created: str,
            name: Optional[str] = None,
            data: Optional[Dict[str, Any]] = None,
    ):
        """
         Create a bucket and update bucket keys. This is a low - level method that should be used by clients that wish to perform operations on buckets such as uploading files to S3

         @param bucket_id - The ID of the bucket to create
         @param type_id - The type of the bucket ( bucket_type )
         @param client - The client that owns the bucket. This is used to determine which buckets are owned by a client and can be used to retrieve information about the client '
         @param hostname - The hostname of the client that owns the bucket
         @param created - The time at which the bucket was created
         @param name - The name of the bucket ( optional ).
         @param data - The data associated with the bucket ( optional )
        """
        BucketModel.create(
            id=bucket_id,
            type=type_id,
            client=client,
            hostname=hostname,
            created=created,
            name=name,
            datastr=json.dumps(data or {}),
        )
        self.update_bucket_keys()

    def update_bucket(
            self,
            bucket_id: str,
            type_id: Optional[str] = None,
            client: Optional[str] = None,
            hostname: Optional[str] = None,
            name: Optional[str] = None,
            data: Optional[dict] = None,
    ) -> None:
        """
         Update a bucket in the storage. This will update the bucket's type hostname name and data if provided.

         @param bucket_id - The ID of the bucket to update.
         @param type_id - The type of the bucket ( bucket_type or bucket_id_url ).
         @param client - The client to use for this bucket. Defaults to the currently logged in client.
         @param hostname - The hostname of the client to use for this bucket. Defaults to the currently logged in client.
         @param name - The name of the bucket as it is stored in the data store.
         @param data - The data to update the bucket with. Must be JSON serializable.

         @return The bucket that was updated or None if the bucket didn't exist
        """
        # Update the bucket with the given id
        if bucket_id in self.bucket_keys:
            bucket = BucketModel.get(BucketModel.key == self.bucket_keys[bucket_id])

            # Set the type of bucket.
            if type_id is not None:
                bucket.type = type_id
            # Set the client to use for the bucket.
            if client is not None:
                bucket.client = client
            # Set the hostname of the bucket.
            if hostname is not None:
                bucket.hostname = hostname
            # Set the name of the bucket.
            if name is not None:
                bucket.name = name
            # Set the data to the bucket.
            if data is not None:
                bucket.datastr = json.dumps(data)  # Encoding data dictionary to JSON

            bucket.save()
        else:
            raise Exception("Bucket did not exist, could not update")

    def delete_bucket(self, bucket_id: str) -> None:
        """
         Deletes a bucket and all events associated with it. This is useful for deleting buckets that are no longer needed

         @param bucket_id - The id of the bucket to delete

         @return True if success False if not ( exception is raised
        """
        # Delete the bucket and update the event model
        if bucket_id in self.bucket_keys:
            EventModel.delete().where(
                EventModel.bucket == self.bucket_keys[bucket_id]
            ).execute()
            BucketModel.delete().where(
                BucketModel.key == self.bucket_keys[bucket_id]
            ).execute()
            self.update_bucket_keys()
        else:
            raise Exception("Bucket did not exist, could not delete")

    def get_metadata(self, bucket_id: str):
        """
         Get metadata for a bucket. This is a wrapper around the get method to make it easier to use in tests

         @param bucket_id - The id of the bucket

         @return A dictionary of bucket metadata or None if the bucket doesn't
        """
        # Get the metadata for a given bucket
        if bucket_id in self.bucket_keys:
            bucket = BucketModel.get(
                BucketModel.key == self.bucket_keys[bucket_id]
            ).json()
            return bucket
        else:
            raise Exception("Bucket did not exist, could not get metadata")

    def insert_one(self, bucket_id: str, event: Event) -> Event:
        """
         Inserts a single event into the database. This is a convenience method for creating and persisting an : class : ` EventModel ` object from a bucket and event.

         @param bucket_id - The bucket to insert into. Must be a string in the form ` ` bucket_keys [ bucket_id ] ` `.
         @param event - The event to insert. Must be a : class : ` Event ` object.

         @return The newly inserted event. Note that you must call save () on the event before you call this
        """
        # e = EventModel.from_event(self.bucket_keys[bucket_id], event)
        ap_name=event.data['app'].split('.')[0]
        # url_link=event.data['url']
        if event.data['title'] != '' and event.data['app'] != '':
            e = EventModel.from_event(self.bucket_keys[bucket_id], event)
            is_exist = self._get_last_event_by_app_title_pulsetime(app=event.application_name, title=event.title)
            if 'afk' not in event.application_name and is_exist and e:
                # logger.info(f'event app: {event.application_name} title: {event.title}')
                is_exist.duration += Decimal(str(e.duration))
                is_exist.server_sync_status = 0  # Convert e.duration to Decimal before addition
                # logger.info(f'after app: {is_exist.id} {is_exist.application_name} title: {is_exist.title}')
                is_exist.save()
                event.id = is_exist.id
                event.duration = float(is_exist.duration)
                return event
            elif e is not None:
                e.server_sync_status = 0
                if not e.url:
                    e.url = ''
                e.save()
                event.id = e.id
                return event
            # else:
            #     logger.warning("Event model has None")
        else:
            logger.warning("None Type object has no server_sync_status attribut or Title were empty for this event")
            return event

    def insert_many(self, bucket_id, events: List[Event]) -> None:
        """
         Insert a list of events into a bucket. This is a wrapper around insert_one to handle events that need to be updated and inserted in one batch

         @param bucket_id - The bucket to insert into
         @param events - The events to insert ( must have id or not
        """
        # NOTE: Events need to be handled differently depending on
        #       if they're upserts or inserts (have id's or not).

        # These events are updates which need to be applied one by one
        events_updates = [e for e in events if e.id is not None]
        # Insert events to the bucket.
        for e in events_updates:
            self.insert_one(bucket_id, e)

        # These events can be inserted with insert_many
        events_dictlist = [
            {
                "bucket": self.bucket_keys[bucket_id],
                "timestamp": event.timestamp,
                "duration": event.duration.total_seconds(),
                "datastr": json.dumps(event.data),
            }
            for event in events
            if event.id is None
        ]

        # Chunking into lists of length 100 is needed here due to SQLITE_MAX_COMPOUND_SELECT
        # and SQLITE_LIMIT_VARIABLE_NUMBER under Windows.
        # See: https://github.com/coleifer/peewee/issues/948
        # Insert events into the database.
        for chunk in chunks(events_dictlist, 100):
            EventModel.insert_many(chunk).execute()

    def update_server_sync_status(self, list_of_ids, new_status):
        EventModel.update(server_sync_status=new_status).where(EventModel.id.in_(list_of_ids)).execute()

    def _get_event(self, bucket_id, event_id) -> Optional[EventModel]:
        """
         Get an event from the database. This is used to find events that need to be sent to Peewee in order to process them

         @param bucket_id - The bucket that the event belongs to
         @param event_id - The id of the event to retrieve

         @return The event or None if not found ( in which case it is None
        """
        try:
            return (
                EventModel.select()
                .where(EventModel.id == event_id)
                .where(EventModel.bucket == self.bucket_keys[bucket_id])
                .get()
            )
        except peewee.DoesNotExist:
            return None

    def _get_dashboard_events(self, starttime, endtime) -> []:
        """
        Get events that match the criteria from the data source. This is a helper function for : meth : ` get_dashboard_events `

        @param starttime - Start time of the search
        @param endtime - End time of the search ( inclusive )

        @return A list of events in chronological order of start
        """

        # Define the raw SQL query with formatting
        raw_query = f"""
            SELECT
                JSON_GROUP_ARRAY(
                    JSON_OBJECT(
                        'start', STRFTIME('%Y-%m-%dT%H:%M:%SZ', timestamp),
                        'end', STRFTIME('%Y-%m-%dT%H:%M:%SZ', DATETIME(timestamp, '+' || duration || ' seconds')),
                        'event_id', id,
                        'duration', duration,
                        'timestamp', timestamp,
                        'data', JSON(CAST(datastr AS TEXT)),
                        'id', id,
                        'bucket_id', bucket_id,
                        'application_name',application_name,
                        'app',app,
                        'title',title,
                        'url',url
                    )
                ) AS formatted_events
            FROM
                eventmodel
            WHERE
                timestamp >= '{starttime}'
                AND timestamp <= '{endtime}'
                AND duration > 30
                AND app NOT LIKE '%afk%'
                AND JSON_EXTRACT(datastr, '$.app') NOT LIKE '%LockApp%'
                AND JSON_EXTRACT(datastr, '$.app') NOT LIKE '%loginwindow%'
                AND IFNULL(JSON_EXTRACT(datastr, '$.status'), '') NOT LIKE '%not-afk%'
            ORDER BY
                timestamp ASC;
        """

        # Execute the raw query
        result = self.db.execute_sql(raw_query)

        # Fetch the results
        rows = result.fetchall()

        # Extract the formatted events from the first row
        formatted_events = json.loads(rows[0][0])

        # Print the formatted events
        return formatted_events

    def _get_non_sync_events(self) -> []:
        """
        Get events that match the criteria from the data source. This is a helper function for : meth : ` get_dashboard_events `

        @param starttime - Start time of the search
        @param endtime - End time of the search ( inclusive )

        @return A list of events in chronological order of start
        """

        # Define the raw SQL query with formatting
        raw_query = f"""
            SELECT
                JSON_GROUP_ARRAY(
                    JSON_OBJECT(
                        'start', STRFTIME('%Y-%m-%dT%H:%M:%SZ', timestamp),
                        'end', STRFTIME('%Y-%m-%dT%H:%M:%SZ', DATETIME(timestamp, '+' || duration || ' seconds')),
                        'event_id', id,
                        'title', JSON_EXTRACT(datastr, '$.title'),
                        'duration', duration,
                        'timestamp', timestamp,
                        'data', JSON(CAST(datastr AS TEXT)),
                        'id', id,
                        'bucket_id', bucket_id,
                        'application_name', application_name
                    )
                ) AS formatted_events
            FROM
                eventmodel
            WHERE
                duration > 30
                AND server_sync_status = 0
                AND JSON_EXTRACT(datastr, '$.app') NOT LIKE '%LockApp%'
                AND JSON_EXTRACT(datastr, '$.app') NOT LIKE '%loginwindow%'
                AND IFNULL(JSON_EXTRACT(datastr, '$.status'), '') NOT LIKE '%not-afk%'
            ORDER BY
                timestamp ASC;
        """

        # Execute the raw query
        result = self.db.execute_sql(raw_query)

        # Fetch the results
        rows = result.fetchall()

        # Extract the formatted events from the first row
        formatted_events = json.loads(rows[0][0])

        # Print the formatted events
        return formatted_events

    def _get_most_used_apps(self, starttime, endtime) -> []:
        """
         Get most used apps in time period. This is used to determine how many apps are in the past and the time spent in each app.

         @param starttime - start time of the period in unix epoch seconds
         @param endtime - end time of the period in unix epoch seconds

         @return list of tuples ( app_name total_hours total_minutes total_seconds total_duration
        """
        # Define the raw SQL query
        raw_query = f"""
            SELECT
                application_name AS app_name,
                STRFTIME('%H', TIME(STRFTIME('%s', '00:00:00') + SUM(duration), 'unixepoch')) AS total_hours,
                STRFTIME('%M', TIME(STRFTIME('%s', '00:00:00') + SUM(duration), 'unixepoch')) AS total_minutes,
                STRFTIME('%S', TIME(STRFTIME('%s', '00:00:00') + SUM(duration), 'unixepoch')) AS total_seconds,
                SUM(duration) AS total_duration,
                url AS url
            FROM
                eventmodel
            WHERE
                timestamp >= '{starttime}'
                AND timestamp <= '{endtime}'
                AND duration > 30
                AND app NOT LIKE '%afk%'
                AND app NOT LIKE '%LockApp%'
                AND app NOT LIKE '%loginwindow%'
            GROUP BY
                app_name;
        """

        # Execute the raw query
        result = self.db.execute_sql(raw_query)

        # Fetch the results
        rows = result.fetchall()

        # Create a list of dictionaries in the desired format
        formatted_results = [{'app': row[0], 'totalHours': row[1], 'totalMinutes': row[2], 'totalSeconds': row[3],
                              'totalDuration': row[4],
                              'url': row[5]} for row in rows]

        # Fetch the results
        return formatted_results

    def _get_last(self, bucket_id) -> EventModel:
        """
         Get the last event in a bucket. This is used to determine when to stop the search in the case of an unresponsive bucket

         @param bucket_id - The bucket to look up

         @return The most up to date EventModel that was added
        """
        return (
            EventModel.select()
            .where(EventModel.bucket == self.bucket_keys[bucket_id])
            .order_by(EventModel.timestamp.desc())
            .get()
        )

    def _get_last_event_by_app_title_pulsetime(self, app, title) -> EventModel:
        # Define the current time and the time 60 seconds ago in UTC
        current_time_utc = datetime.utcnow()
        time_60_seconds_ago_utc = current_time_utc - timedelta(seconds=70)
        return (
            EventModel
            .select()
            .where((EventModel.application_name == app) & (EventModel.title == title) & (
                    EventModel.timestamp >= time_60_seconds_ago_utc))
            .order_by(EventModel.timestamp.desc())
            .first()
        )

    def _get_last_event_by_app_title(self, app, title) -> EventModel:
        return (
            EventModel
            .select()
            .where((EventModel.application_name == app) & (EventModel.title == title))
            .order_by(EventModel.timestamp.desc())
            .first()
        )

    def _get_last_event_by_app_url(self, app, url) -> EventModel:
        return (
            EventModel
            .select()
            .where((EventModel.application_name == app) & (EventModel.url == url))
            .order_by(EventModel.timestamp.desc())
            .first()
        )

    def replace_last(self, bucket_id, event):
        """
         Replaces the last event in the bucket with the given event. This is useful for events that have been added in the middle of a batch.

         @param bucket_id - The bucket to replace the last event in.
         @param event - The event to replace. Must be a : class : ` ~mediadrop. event. Event ` instance.

         @return The event with the latest data replaced with the given
        """
        try:
            e = None
            if event.url:
                e = self._get_last_event_by_app_url(event.application_name, event.url)
            else:
                e = self._get_last_event_by_app_title(event.application_name, event.title)
            if e:
                # e.timestamp = event.timestamp
                e.duration = event['duration'].total_seconds()
                # e.datastr = json.dumps(event.data)
                e.server_sync_status = 0
                e.save()
                event.id = e.id
        except Exception as ef:
            logger.error(f"replace_event error: {ef}")
            logger.error(f"last_event error event: {e}")
            logger.error(f"replace_event error event: {event}")
        return event

    def delete(self, bucket_id, event_id):
        """
         Delete an event from a bucket. This is useful for deleting events that are no longer associated with a bucket

         @param bucket_id - The id of the bucket to delete the event from
         @param event_id - The id of the event to delete

         @return The number of rows deleted or None if the event wasn't
        """
        return (
            EventModel.delete()
            .where(EventModel.id == event_id)
            .where(EventModel.bucket == self.bucket_keys[bucket_id])
            .execute()
        )

    def replace(self, bucket_id, event_id, event):
        """
         Replaces an event with a new one. This is useful when you want to replace a previously existing event in the event store.

         @param bucket_id - The ID of the bucket to replace the event in.
         @param event_id - The ID of the event to replace.
         @param event - The event to replace. It must have a timestamp duration and datastr set.

         @return The updated event object. note :: The event is updated in - place
        """
        e = self._get_event(bucket_id, event_id)
        e.timestamp = event.timestamp
        e.duration = event.duration.total_seconds()
        e.datastr = json.dumps(event.data)
        e.server_sync_status = 0
        e.save()
        event.id = e.id
        return event

    def get_event(
            self,
            bucket_id: str,
            event_id: int,
    ) -> Optional[Event]:
        """
        Fetch a single event from a bucket.
        """
        res = self._get_event(bucket_id, event_id)
        return Event(**EventModel.json(res)) if res else None

    def get_events(
            self,
            bucket_id: str,
            limit: int,
            starttime: Optional[datetime] = None,
            endtime: Optional[datetime] = None,
    ):
        """
        Fetch events from a certain bucket, optionally from a given range of time.

        Example raw query:

            SELECT strftime(
              "%Y-%m-%d %H:%M:%f+00:00",
              ((julianday(timestamp) - 2440587.5) * 86400),
              'unixepoch'
            )
            FROM eventmodel
            WHERE eventmodel.timestamp > '2021-06-20'
            LIMIT 10;

        """
        if limit == 0:
            return []
        q = (
            EventModel.select()
            .where(EventModel.bucket == self.bucket_keys[bucket_id])
            .order_by(EventModel.timestamp.desc())
            .limit(limit)
        )

        q = self._where_range(q, starttime, endtime)

        res = q.execute()
        events = [Event(**e) for e in list(map(EventModel.json, res))]
        # Trim events that are out of range (as done in aw-server-rust)
        # TODO: Do the same for the other storage methods
        for e in events:
            if starttime:
                if e.timestamp < starttime:
                    e_end = e.timestamp + e.duration
                    e.timestamp = starttime
                    e.duration = e_end - e.timestamp
            if endtime:
                if e.timestamp + e.duration > endtime:
                    e.duration = endtime - e.timestamp

        return events

    def get_last_event_by_app_title_pulsetime(self, app, title) -> EventModel:
        return self._get_last_event_by_app_title_pulsetime(app=app, title=title)

    def get_most_used_apps(
            self,
            starttime: Optional[datetime] = None,
            endtime: Optional[datetime] = None,
    ) -> []:
        """
         Get most used apps in time period. This is a wrapper around _get_most_used_apps

         @param starttime - start time of the period ( optional ). If not specified will default to now
         @param endtime - end time of the period ( optional ). If not specified will default to now

         @return a list of app objects sorted by time ( oldest to newest
        """
        return self._get_most_used_apps(starttime, endtime)

    def get_dashboard_events(
            self,
            starttime: Optional[datetime] = None,
            endtime: Optional[datetime] = None,
    ) -> []:
        """
         Get a list of dashboard events. This is a wrapper around _get_dashboard_events that does not require a start and end datetime

         @param starttime - The start datetime to get events from
         @param endtime - The end datetime to get events to ( inclusive )

         @return A list of : class : ` DashboardEvent `
        """
        return self._get_dashboard_events(starttime, endtime)

    def get_non_sync_events(
            self
    ) -> []:

        return self._get_non_sync_events()

    def get_eventcount(
            self,
            bucket_id: str,
            starttime: Optional[datetime] = None,
            endtime: Optional[datetime] = None,
    ) -> int:
        """
         Get the number of events in a bucket. This is useful for determining how many events have been added since the start of the interval.

         @param bucket_id - The bucket to look up events in
         @param starttime - The start of the interval to look up events in
         @param endtime - The end of the interval to look up events in

         @return The number of events in the given time range in
        """
        q = EventModel.select().where(EventModel.bucket == self.bucket_keys[bucket_id])
        q = self._where_range(q, starttime, endtime)
        return q.count()

    def _where_range(
            self,
            q,
            starttime: Optional[datetime] = None,
            endtime: Optional[datetime] = None,
    ):
        """
         Filter a query to a range of events. This is a helper for _get_events to add support for time ranges

         @param q - query to filter ( sqlalchemy. sql. expression. WHERE )
         @param starttime - start time of the range ( datetime. datetime )
         @param endtime - end time of the range ( datetime. datetime )

         @return query with filters applied to the start and end time
        """
        # Important to normalize datetimes to UTC, otherwise any UTC offset will be ignored
        # Set the current time zone to UTC.
        if starttime:
            starttime = starttime.astimezone(timezone.utc)
        # Return the end time of the current time zone.
        if endtime:
            endtime = endtime.astimezone(timezone.utc)

        # This is a slow query to avoid slow queries.
        if starttime:
            # Faster WHERE to speed up slow query below, leads to ~2-3x speedup
            # We'll assume events aren't >24h
            q = q.where(starttime - timedelta(hours=24) <= EventModel.timestamp)

            # This can be slow on large databases...
            # Tried creating various indexes and using SQLite's unlikely() function, but it had no effect
            q = q.where(
                starttime <= dt_plus_duration(EventModel.timestamp, EventModel.duration)
            )
        # Return a query to the database that have a timestamp greater than the endtime.
        if endtime:
            q = q.where(EventModel.timestamp <= endtime)

        return q

    def save_settings(self, code, value_dict):
        """
        Save or update a setting in the database. If the setting with the given code exists, it will be updated.
        Otherwise, a new setting will be created.

        Parameters:
        - code (str): The unique code for the setting.
        - value_dict (dict): The value of the setting, provided as a dictionary which will be serialized to JSON.

        Returns:
        - SettingsModel instance of the saved or updated setting.
        """
        value_json = json.dumps(value_dict)  # Convert the dictionary to a JSON string
        setting, created = SettingsModel.get_or_create(code=code, defaults={'value': value_json})
        if not created:
            setting.value = value_json
            setting.save()
            db_cache.store(settings_cache_key, self.retrieve_all_settings())
        return setting

    def retrieve_setting(self, code):
        """
        Retrieve a single setting from the database by its code.

        Parameters:
        - code (str): The unique code for the setting.

        Returns:
        - The value of the setting as a dictionary if the setting exists; otherwise, None.
        """
        try:
            setting = SettingsModel.get(SettingsModel.code == code)
            return json.loads(setting.value)  # Convert the JSON string back to a dictionary
        except SettingsModel.DoesNotExist:
            return None

    def retrieve_all_settings(self):
        """
        Retrieve all settings from the database, deserializing each value from a JSON string.
        Handles cases where the value might not be a valid JSON string.
        """
        all_settings = {}
        for setting in SettingsModel.select():
            try:
                if setting.code != "profilePic":
                    # Attempt to deserialize each value from a JSON string
                    all_settings[setting.code] = json.loads(setting.value) if setting.value else None
            except json.JSONDecodeError as e:
                # Log the error and skip this setting or set a default value
                logger.error(f"Error decoding JSON for setting '{setting.code}': {e}")
                all_settings[setting.code] = None  # Or set a default value if appropriate
        return all_settings

    def update_setting(code, new_value_dict):
        """
        Update the value of an existing setting in the database.

        Parameters:
        - code (str): The unique code for the setting to update.
        - new_value_dict (dict): The new value for the setting, provided as a dictionary.

        Returns:
        - The updated SettingsModel instance if the update was successful; otherwise, None.
        """
        try:
            setting = SettingsModel.get(SettingsModel.code == code)
            setting.value = json.dumps(new_value_dict)  # Serialize the new value to JSON
            setting.save()
            return setting
        except SettingsModel.DoesNotExist:
            return None

    def save_application_details(self, application_details):
        """
        Save or update application details in the database.
        :param application_details: A dictionary containing the details of the application.
        :return: The saved or updated ApplicationModel object.
        """
        try:
            if 'url' in application_details and application_details['url']:
                application = ApplicationModel.get_or_none(url=application_details['url'])
                if application:
                    # Update existing application details
                    for key, value in application_details.items():
                        setattr(application, key, value)
                    application.updated_at = datetime.now()
                    application.save()
                else:
                    application = ApplicationModel.create(**application_details)
            elif 'name' in application_details and application_details['name']:
                existing_application = ApplicationModel.get_or_none(name=application_details['name'])
                if existing_application:
                    # Update existing application details
                    for key, value in application_details.items():
                        setattr(existing_application, key, value)
                    existing_application.updated_at = datetime.now()
                    existing_application.save()
                    application = existing_application
                else:
                    # Create a new application
                    application = ApplicationModel.create(**application_details)
            else:
                raise ValueError("Either 'url' or non-empty 'name' must be provided in application_details.")

            # Refresh the application names after saving
            self.retrieve_application_names()

            return application
        except peewee.IntegrityError as e:
            logger.error(f"Integrity error while saving application details: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving application details: {e}")
            raise

    def retrieve_application_details(self):
        """
        Retrieve all application details from the database.
        :return: A JSON-serializable list of dictionaries with all application details if found, otherwise None.
        """
        try:
            # Use a query to retrieve all application details
            query = ApplicationModel.select()
            application_details = [model_to_dict(app) for app in query]

            # Serialize datetime objects to strings
            for app_detail in application_details:
                for key, value in app_detail.items():
                    if isinstance(value, datetime):
                        app_detail[key] = value.strftime('%Y-%m-%d %H:%M:%S')

            return application_details if application_details else None
        except DoesNotExist:
            return None

    def retrieve_application_names(self):
        """
        Retrieve all application names and blocked statuses from the database.
        :return: A JSON-serializable list of dictionaries with application names and blocked statuses if found,
                 otherwise None.
        """
        application_details = {}
        try:
            # Retrieve application names and blocked statuses where name is not None
            app_query_results = ApplicationModel.select(ApplicationModel.name, ApplicationModel.is_blocked) \
                .where((ApplicationModel.name.is_null(False)) & (ApplicationModel.name != ""))

            # Convert the query results to a list of dictionaries
            application_details['app'] = [{'name': result.name, 'is_blocked': result.is_blocked}
                                          for result in app_query_results]

            # Retrieve URLs and blocked statuses where URL is not None and is_blocked is True
            url_query_results = ApplicationModel.select(ApplicationModel.url, ApplicationModel.is_blocked) \
                .where((ApplicationModel.url.is_null(False)) & (ApplicationModel.is_blocked == True) & (
                    ApplicationModel.url != ""))

            # Convert the query results to a list of dictionaries
            application_details['url'] = [{'url': result.url, 'is_blocked': result.is_blocked}
                                          for result in url_query_results]
            db_cache.update(application_cache_key, application_details)
            return application_details  # Return the list of application details
        except Exception as e:
            logger.error(f"An unexpected error occurred while retrieving application names: {e}")
            raise

    def delete_application_details(self, application_id):
        try:
            existing_instance = ApplicationModel.get_or_none(id=application_id)
            if existing_instance:
                existing_instance.delete_instance()
                return existing_instance
            else:
                # Handle the case where the instance with the provided name doesn't exist
                return None
        except DoesNotExist:
            # Handle the case where the instance with the provided name doesn't exist
            return None

    def get_blocked(self):
        """
        Retrieve all application names and blocked statuses from the database.
        :return: A JSON-serializable list of dictionaries with application names and blocked statuses if found,
                 otherwise None.
        """
        application_details = {}
        try:
            # Retrieve application names and blocked statuses where name is not None
            app_query_results = ApplicationModel.select(ApplicationModel.name, ApplicationModel.is_blocked) \
                .where((ApplicationModel.name.is_null(False)) & (ApplicationModel.name != "") & (
                    ApplicationModel.is_blocked == True))

            # Convert the query results to a list of dictionaries
            application_details['app'] = [{'name': result.name, 'is_blocked': result.is_blocked}
                                          for result in app_query_results]

            # Retrieve URLs and blocked statuses where URL is not None and is_blocked is True
            url_query_results = ApplicationModel.select(ApplicationModel.url, ApplicationModel.is_blocked) \
                .where((ApplicationModel.url.is_null(False)) & (ApplicationModel.is_blocked == True) & (
                    ApplicationModel.url != ""))

            # Convert the query results to a list of dictionaries
            application_details['url'] = [{'url': result.url, 'is_blocked': result.is_blocked}
                                          for result in url_query_results]
            db_cache.update(application_cache_key, application_details)
            return application_details  # Return the list of application details
        except Exception as e:
            logger.error(f"An unexpected error occurred while retrieving application names: {e}")
            raise

    def launch_application_start(self):
        settings = db_cache.retrieve(settings_cache_key)
        logger.info(settings)
        # The code is checking if the value of the 'launch' key in the settings dictionary is truthy
        # (evaluates to True), and if it is, it calls the function launch_app().
        if settings['launch'] and sys.platform == "darwin" and not check_startup_status() :
            launch_app()
        elif settings['launch'] and sys.platform == "win32" and not check_startup_status() :
            create_shortcut()

    def afk_status(self):
        manager = Manager()
        settings = db_cache.retrieve(settings_cache_key)
        status_list = manager.status()
        print(status_list)
        for watchers in status_list:
            if watchers['watcher_name'] == "aw-watcher-afk" and watchers['Watcher_status']:
                if settings['idle_time']:
                    return True
                else:
                    return False
            else:
                return False

    # def save_date(self):
    #     settings, created = SettingsModel.get_or_create(code="System Date",
    #                                                     defaults={'value': datetime.now().date()})
    #     stored_date = datetime.strptime(SettingsModel.get(SettingsModel.code == "System Date").value, "%Y-%m-%d").date()
    #     if not created:
    #         # If the settings object already exists, update the code and value
    #         settings.code = "System Date"
    #         if datetime.now().date() > stored_date:
    #             settings.value = datetime.now(pytz.UTC).date()
    #             settings.save()  # Save the changes to the database
    #         else:
    #             logger.info("Date has been changed")
    #
    # def retrieve_date(self):
    #     return datetime.strptime(SettingsModel.get(SettingsModel.code == "System Date").value, "%Y-%m-%d").date()
