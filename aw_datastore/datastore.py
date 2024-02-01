import logging
from datetime import datetime, timedelta, timezone
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

from aw_core.models import Event

from .storages import AbstractStorage, peewee

logger = logging.getLogger(__name__)


class Datastore:
    def __init__(
        self,
        storage_strategy: Callable[..., AbstractStorage],
        testing=False,
        **kwargs,
    ) -> None:
        """
         Initialize the datastore. This is the method that must be called in order to initialize the datastore. If you don't want to call this method you have to do it yourself.

         @param storage_strategy - A callable that takes no arguments and returns : class : ` AbstractStorage `
         @param testing - A boolean indicating whether or not this datastore is for
        """
        self.logger = logger.getChild("Datastore")
        self.bucket_instances: Dict[str, Bucket] = dict()

        self.storage_strategy = storage_strategy(testing=testing, **kwargs)

    def __repr__(self):
        """
         Returns a string representation of the datastore. This is used to print the object to the console. It should be noted that the string representation of the datastore is the same as the string representation of the StorageStrategy used to create it.


         @return A string representation of the datastore object to be printed to the console in the form of a human - readable
        """
        return "<Datastore object using {}>".format(
            self.storage_strategy.__class__.__name__
        )

    def init_db(self) -> bool:
        """
         Initialize database. This is called after all objects have been added to the storage and before any data is stored.


         @return True if initialization was successful False otherwise ( in which case we don't need to call this any more
        """
        return self.storage_strategy.init_db()

    def __getitem__(self, bucket_id: str) -> "Bucket":
        """
         Get a bucket from the database. This is the inverse of __getitem__. If the bucket doesn't exist in the database a KeyError is raised

         @param bucket_id - The id of the bucket to get

         @return The bucket's object representation of the bucket_id if it exists in the database otherwise a KeyError is
        """
        # If this bucket doesn't have a initialized object, create it
        # Create a new Bucket object for the given bucket_id.
        if bucket_id not in self.bucket_instances:
            # If the bucket exists in the database, create an object representation of it
            # Create a new Bucket object for the given bucket_id.
            if bucket_id in self.buckets():
                bucket = Bucket(self, bucket_id)
                self.bucket_instances[bucket_id] = bucket
            else:
                self.logger.error(
                    "Cannot create a Bucket object for {} because it doesn't exist in the database".format(
                        bucket_id
                    )
                )
                raise KeyError

        return self.bucket_instances[bucket_id]

    def save_settings(self,code, value) -> None:
        """
         Save settings to storage. This is a low - level method to be used by subclasses when they want to save a set of settings that have been loaded from a file or a configuration file.

         @param settings_id - id of the settings to save.
         @param settings_dict - dictionary of settings to save. Keys must match the names of the settings in the settings_dict.

         @return True if successful False otherwise. Raises : py : exc : ` ~errbot. backends. base. BackendError ` if there is a problem
        """
        self.storage_strategy.save_settings(code, value)

    def retrieve_settings(self, code) -> dict:
        """
         Retrieves settings from the storage strategy. This is a low - level method to be used by subclasses that need to retrieve settings from their own storage strategy

         @param settings_id - id of the settings to retrieve

         @return dict of settings or None if not found or could not be retrieved from the storage strategy for any reason
        """
        return self.storage_strategy.retrieve_settings(code)

    def save_application_details(self, application_details):
        return self.storage_strategy.save_application_details(application_details=application_details)
    def retrieve_application_details(self) -> dict:
        return self.storage_strategy.retrieve_application_details()
    def create_bucket(
        self,
        bucket_id: str,
        type: str,
        client: str,
        hostname: str,
        created: datetime = datetime.now(timezone.utc),
        name: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> "Bucket":
        """
         Create a bucket. This will be used by : meth : ` ~flask. Bucket. create `

         @param bucket_id - The ID of the bucket to create
         @param type - The type of the bucket
         @param client - The client that owns the bucket ( s )
         @param hostname - The hostname of the client that owns the bucket ( s )
         @param created - The time at which the bucket was created ( defaults to now )
         @param name - The name of the bucket ( defaults to None )
         @param data - The data associated with the bucket ( defaults to None )

         @return The newly created bucket ( : class : ` ~flask. Bucket ` ) versionadded :: 1.
        """
        self.logger.info(f"Creating bucket '{bucket_id}'")
        self.storage_strategy.create_bucket(
            bucket_id, type, client, hostname, created.isoformat(), name=name, data=data
        )
        return self[bucket_id]

    def update_bucket(self, bucket_id: str, **kwargs):
        """
         Update a bucket. This is a low - level method that should be used by consumers to ensure consistency of bucket and its content.

         @param bucket_id - The ID of the bucket to update.

         @return An instance of novaclient. base. TupleWithMeta with metadata about the updated bucket and a boolean indicating success or failure
        """
        self.logger.info(f"Updating bucket '{bucket_id}'")
        return self.storage_strategy.update_bucket(bucket_id, **kwargs)

    def delete_bucket(self, bucket_id: str):
        """
         Delete a bucket. This is a no - op if the bucket doesn't exist. Otherwise it will call

         @param bucket_id - The ID of the bucket to delete.

         @return True if the bucket was deleted False otherwise. note :: This method does not return a value. To get the bucket's value use : py : meth : ` get_bucket `
        """
        self.logger.info(f"Deleting bucket '{bucket_id}'")
        # Remove the bucket instance from the list of bucket instances.
        if bucket_id in self.bucket_instances:
            del self.bucket_instances[bucket_id]
        return self.storage_strategy.delete_bucket(bucket_id)

    def buckets(self):
        """
         Get a list of buckets to use for this storage. This is the same as : meth : ` ~google. cloud. bigquery. storage. StorageStrategy. buckets ` but for a different strategy.


         @return A list of bucket names to use for this storage or an empty list if there are no buckets in
        """
        return self.storage_strategy.buckets()

    def get_most_used_apps(self, starttime, endtime) -> []:
        """
         Get most used apps in time period. This is a wrapper around the : py : meth : ` ~plexapi. storage. StorageStrategy. get_most_used_apps ` method of the storage strategy

         @param starttime - start time of the period
         @param endtime - end time of the period ( inclusive )

         @return list of apps that were used in time period ( s ) or empty list if no apps were used
        """
        return self.storage_strategy.get_most_used_apps(starttime, endtime)

    def get_dashboard_events(self, starttime, endtime) -> []:
        """
         Get dashboard events between start and end time. This is a wrapper around StorageStrategy. get_dashboard_events to be used by subclasses

         @param starttime - Start time of the time range to query
         @param endtime - End time of the time range to query

         @return A list of dashboard events in chronological order ( oldest first ) or empty list if there are no
        """
        return self.storage_strategy.get_dashboard_events(starttime, endtime)

    def get_non_sync_events(self) -> []:
        return self.storage_strategy.get_non_sync_events()

    def update_server_sync_status(self, list_of_ids, new_status):
        return self.storage_strategy.update_server_sync_status(list_of_ids, new_status)


class Bucket:
    def __init__(self, datastore: Datastore, bucket_id: str) -> None:
        """
         Initialize the bucket. This is called by the : class : ` Bucket ` constructor to initialize the bucket.

         @param datastore - The datastore to use for this bucket. Must be a subclass of : class : ` ~buck. datastore. Datastore `.
         @param bucket_id - The id of the bucket. If it's a bucket this is the bucket's ID.

         @return None or an error object that can be raised to signal the failure of the initialization. The error object is a subclass of
        """
        self.logger = logger.getChild("Bucket")
        self.ds = datastore
        self.bucket_id = bucket_id

    def metadata(self) -> dict:
        """
         Get metadata for this bucket. This is a low - level method that should be used by subclasses to get a dictionary of key / value pairs that are suitable for storage in the current environment.


         @return A dictionary of key / value pairs that are suitable for storage in the current environment or None if no metadata is available
        """
        return self.ds.storage_strategy.get_metadata(self.bucket_id)

    def get(
        self,
        limit: int = -1,
        starttime: Optional[datetime] = None,
        endtime: Optional[datetime] = None,
    ) -> List[Event]:
        """
         Get events from the storage strategy. This is a low - level method to be used by clients who don't need to worry about time handling.

         @param limit - max number of events to return in one request
         @param starttime - start time of events to return in milliseconds
         @param endtime - end time of events to return in milliseconds

         @return list of : class : ` Event ` objects sorted by timestamp in descending order of creation / modification time
        """
        """Returns events sorted in descending order by timestamp"""
        # Resolution is rounded down since not all datastores like microsecond precision
        # Get the current time in microseconds.
        if starttime:
            starttime = starttime.replace(
                microsecond=1000 * int(starttime.microsecond / 1000)
            )
        # If endtime is not None then the end time is replaced with the same time.
        if endtime:
            # Rounding up here in order to ensure events aren't missed
            # second_offset and microseconds modulo required since replace() only takes microseconds up to 999999 (doesn't handle overflow)
            milliseconds = 1 + int(endtime.microsecond / 1000)
            second_offset = int(milliseconds / 1000)  # usually 0, rarely 1
            microseconds = (
                1000 * milliseconds
            ) % 1000000  # will likely just be 1000 * milliseconds, if it overflows it would become zero
            endtime = endtime.replace(microsecond=microseconds) + timedelta(
                seconds=second_offset
            )

        return self.ds.storage_strategy.get_events(
            self.bucket_id, limit, starttime, endtime
        )

    def get_by_id(self, event_id) -> Optional[Event]:
        """
         Gets an event by ID. This is a low - level method to be used by subclasses that need to retrieve events from their storage strategy.

         @param event_id - The ID of the event to retrieve.

         @return The : class : ` Event ` with the given ID or ` ` None ` ` if not found
        """
        """Will return the event with the provided ID, or None if not found."""
        return self.ds.storage_strategy.get_event(self.bucket_id, event_id)

    def get_eventcount(
        self, starttime: Optional[datetime] = None, endtime: Optional[datetime] = None
    ) -> int:
        """
         Get the number of events in this bucket. This is a wrapper around StorageStrategy. get_eventcount

         @param starttime - start time of the time range to query
         @param endtime - end time of the time range to query

         @return the number of events in this bucket between starttime and endtime or - 1 if there are no events in
        """
        return self.ds.storage_strategy.get_eventcount(
            self.bucket_id, starttime, endtime
        )

    def insert(self, events: Union[Event, List[Event]]) -> Optional[Event]:
        """
         Inserts one or more events into the bucket. This is a low - level method that does not check if the events are indeed valid and can be used to insert a new event or to update an existing event

         @param events - Event or list of events to insert

         @return Event with its id assigned or None if there was no event to be inserted ( in which case it is returned
        """
        """
        Inserts one or several events.
        If a single event is inserted, return the event with its id assigned.
        If several events are inserted, returns None. (This is due to there being no efficient way of getting ids out when doing bulk inserts with some datastores such as peewee/SQLite)
        """

        # events.data = peewee.decrypt(events.data)
        # NOTE: Should we keep the timestamp checking?
        warn_older_event = False
        # Get last event for timestamp check after insert
        # If warn_older_event is true the last event is the last event in the list.
        if warn_older_event:
            last_event_list = self.get(1)
            last_event = None
            # This function is called when the last event is received.
            if last_event_list:
                last_event = last_event_list[0]

        now = datetime.now(tz=timezone.utc)

        inserted: Optional[Event] = None

        # Call insert
        # Insert events into the bucket.
        if isinstance(events, Event):
            oldest_event: Optional[Event] = events
            # Check if the event inserted into the bucket reaches the future.
            if events.timestamp + events.duration > now:
                self.logger.warning(
                    "Event inserted into bucket {} reaches into the future. Current UTC time: {}. Event data: {}".format(
                        self.bucket_id, str(now), str(events)
                    )
                )
            inserted = self.ds.storage_strategy.insert_one(self.bucket_id, events)
            # assert inserted
        elif isinstance(events, list):
            events.data = peewee.decrypt(events.data)
            # Returns oldest event in the list of events.
            if events:
                oldest_event = sorted(events, key=lambda k: k["timestamp"])[0]
            else:  # pragma: no cover
                oldest_event = None
            # Check if the event data has been inserted into the future.
            for event in events:
                # Check if the event is inserted into the bucket.
                if event.timestamp + event.duration > now:
                    self.logger.warning(
                        "Event inserted into bucket {} reaches into the future. Current UTC time: {}. Event data: {}".format(
                            self.bucket_id, str(now), str(event)
                        )
                    )
            self.ds.storage_strategy.insert_many(self.bucket_id, events)
        else:
            raise TypeError

        # Warn if timestamp is older than last event
        # If warn_older_event and oldest_event have a older timestamp than last_event. timestamp
        if warn_older_event and last_event and oldest_event:
            # Insert an event that has a older timestamp than the last event.
            if oldest_event.timestamp < last_event.timestamp:  # pragma: no cover
                self.logger.warning(
                    f"""Inserting event that has a older timestamp than previous event!
Previous: {last_event}
Inserted: {oldest_event}"""
                )

        return inserted

    def delete(self, event_id):
        """
         Delete an event from the storage. This is equivalent to calling : meth : ` delete_bucket ` with the bucket_id and event_id as arguments.

         @param event_id - The id of the event to delete.

         @return True if the operation succeeded False otherwise. note :: It is possible to delete a non - existent event
        """
        return self.ds.storage_strategy.delete(self.bucket_id, event_id)

    def replace_last(self, event):
        """
         Replace the last event in the bucket with the given event. This is a no - op if there is no event to replace.

         @param event - The event to replace the last event in the bucket with.

         @return The event that was replaced or None if no event was replaced ( in which case the event will be returned
        """
        return self.ds.storage_strategy.replace_last(self.bucket_id, event)

    def replace(self, event_id, event):
        """
         Replace an event with a new one. This is a no - op if the event doesn't exist

         @param event_id - The id of the event to replace
         @param event - The event to replace the old one with.

         @return True if the operation succeeded False otherwise. note :: For more details see the : py : meth : ` CloudStorage. StorageStrategy. replace `
        """
        return self.ds.storage_strategy.replace(self.bucket_id, event_id, event)
