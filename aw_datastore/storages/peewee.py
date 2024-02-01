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

import pytz
import tldextract
from playhouse.shortcuts import model_to_dict

from aw_core.cache import cache_user_credentials

if sys.platform == "win32":
    _module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
    os.add_dll_directory(_module_dir)
elif sys.platform == "darwin":
    _module_dir = os.path.dirname(os.path.realpath(__file__))
    _parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(os.path.join(_module_dir, os.pardir))))
    libsqlcipher_path = _parent_dir
    openssl = ctypes.cdll.LoadLibrary(libsqlcipher_path + '/libcrypto.3.dylib')
    libsqlcipher = ctypes.cdll.LoadLibrary(libsqlcipher_path + '/libsqlcipher.0.dylib')

from aw_core.util import decrypt_uuid, load_key, start_all_module, stop_all_module
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


import platform


class EventModel(BaseModel):
    id = AutoField()
    bucket = ForeignKeyField(BucketModel, backref="events", index=True)
    timestamp = DateTimeField(index=True, default=datetime.now)
    duration = DecimalField()
    datastr = CharField()
    app = CharField()
    title = CharField()
    url = CharField()
    application_name = CharField()
    server_sync_status = IntegerField(default=0)

    @classmethod
    def from_event(cls, bucket_key, event: Event):
        """
        Create an EventModel instance from a Cloud Pub/Sub event.

        @param cls - The class to use for the new event.
        @param bucket_key - The key of the bucket to use for the new event.
        @param event - The event to create the event from. Must have a non-empty Event attribute.

        @return The newly created EventModel instance
        """
        system = platform.system()

        if not event.data.get('url'):
            if system == 'Darwin':  # macOS
                app_name = event.data.get('app')
            else:
                app_name = event.data.get('title')
        else:
            app_name = tldextract.extract(event.data.get('url', '')).domain

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


import platform


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

        @return The newly created EventModel instance
        """
        if not event.data.get('url'):
            app_name = event.data.get('app', '')
            if ".exe" in app_name.lower():
                app_name = re.sub(r'\.exe$', '', app_name)
        else:
            app_name = tldextract.extract(event.data.get('url', '')).domain

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
    code = CharField()
    value = CharField()

    @classmethod
    def from_settings(cls, code, value):
        return cls(
            code=code,
            value=value,
        )

    def json(self):
        """
        Convert the model instance to a JSON-compatible dictionary.
        :return: A dictionary representation of the settings.
        """
        return {
            "id": self.id,
            "code": self.code,
            "value": self.value,

        }


class ApplicationModel(BaseModel):
    id = AutoField()
    type = CharField()
    name = CharField(null=False, unique=True)
    alias = CharField(null=True)
    is_blocked = BooleanField(default=False)
    is_ignore_idle_time = BooleanField(default=False)
    color = CharField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    @classmethod
    def from_application_details(cls, application_details):
        existing_instance = cls.get_or_none(name=application_details.get("name", ""))
        if existing_instance is None:
            current_time = datetime.now()
            return cls(
                type=application_details.get("type", ""),
                name=application_details.get("name", ""),
                alias=application_details.get("alias", ""),
                is_blocked=application_details.get("is_blocked", False),
                is_ignore_idle_time=application_details.get("idle_time_ignored", False),
                color=application_details.get("color", ""),
                created_at=current_time,
                updated_at=current_time,
            )
        else:
            existing_instance.type = application_details.get("type", "")
            existing_instance.alias = application_details.get("alias", "")
            existing_instance.is_blocked = application_details.get("is_blocked", False)
            existing_instance.is_ignore_idle_time = application_details.get("idle_time_ignored", False)
            existing_instance.color = application_details.get("color", "")
            existing_instance.updated_at = datetime.now()
            existing_instance.save()
            return existing_instance

    def json(self):
        """
        Convert the model instance to a JSON-compatible dictionary.
        :return: A dictionary representation of the settings.
        """
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "alias": self.alias,
            "is_blocked": self.is_blocked,
            "is_ignore_idle_time": self.is_ignore_idle_time,
            "color": self.color,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S'),  # Convert to a string in the desired format
            "updated_at": self.updated_at.strftime('%Y-%m-%d %H:%M:%S'),  # Convert to a string in the desired format
        }


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
        cache_key = "sundial"
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
                        + ("-testing" if testing else "")
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

            # Stop all modules that have been changed.
            if database_changed:
                stop_all_module()
            start_all_module()

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
        e = EventModel.from_event(self.bucket_keys[bucket_id], event)
        e.server_sync_status = 0
        if not e.url:
            e.url = ''
        e.save()
        event.id = e.id
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
                        'bucket_id', bucket_id
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

    def replace_last(self, bucket_id, event):
        """
         Replaces the last event in the bucket with the given event. This is useful for events that have been added in the middle of a batch.

         @param bucket_id - The bucket to replace the last event in.
         @param event - The event to replace. Must be a : class : ` ~mediadrop. event. Event ` instance.

         @return The event with the latest data replaced with the given
        """
        e = self._get_last(bucket_id)
        e.timestamp = event.timestamp
        e.duration = event.duration.total_seconds()
        e.datastr = json.dumps(event.data)
        e.server_sync_status = 0
        e.save()
        event.id = e.id
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

    def save_settings(self, code, value):
        """
        Save or update settings in the database.
        :param settings_id: The unique identifier for the settings.
        :param code: The code associated with the settings.
        :param value: The value of the settings to be saved.
        :return: The saved or updated settings object.
        """
        try:
            # Attempt to retrieve an existing settings object or create a new one if it doesn't exist
            settings, created = SettingsModel.get_or_create(code=code,
                                                            defaults={'value': value})

            if not created:
                # If the settings object already exists, update the code and value
                settings.code = code
                settings.value = value  # Set value as empty string if it's empty
                settings.save()  # Save the changes to the database

            return settings  # Return the settings object, whether it was created or updated
        except peewee.IntegrityError as e:
            logger.error(f"Integrity error while saving settings: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving settings: {e}")
            raise

    def retrieve_settings(self, code):
        """
        Retrieve settings from the database.
        :param settings_id: The unique identifier for the settings.
        :return: A dictionary of the settings if found, otherwise None.
        """
        try:
            settings = SettingsModel.get(SettingsModel.code == code)
            return settings.value
        except SettingsModel.DoesNotExist:
            return None

    def save_application_details(self, application_details):
        """
        Save or update application details in the database.
        :param application_details: A dictionary containing the details of the application.
        :return: The saved or updated ApplicationModel object.
        """
        try:
            # Attempt to retrieve an existing application object or create a new one if it doesn't exist
            application, created = ApplicationModel.get_or_create(name=application_details['name'],
                                                                  defaults=application_details)

            if not created:
                # If the application object already exists, update its details
                for key, value in application_details.items():
                    setattr(application, key, value)
                application.updated_at = datetime.now()  # Update the 'updated_at' field to current time
                application.save()  # Save the changes to the database

            return application  # Return the application object, whether it was created or updated
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
        except ApplicationModel.DoesNotExist:
            return None

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
