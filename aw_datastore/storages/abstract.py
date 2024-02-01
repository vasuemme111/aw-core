from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from aw_core.models import Event


class AbstractStorage(metaclass=ABCMeta):
    """
    Interface for storage methods.
    """

    sid = "1429"

    @abstractmethod
    def __init__(self, testing: bool) -> None:
        """
         Initialize the instance. This is called by __init__ and should not be called directly. The test method is used to determine if the tests are run or not

         @param testing - True if testing False if not

         @return A tuple of ( success_flag failure_flag ) where success_flag is True if we are running in testing mode and failure_flag is a boolean indicating if we are
        """
        self.testing = True
        raise NotImplementedError

    @abstractmethod
    def init_db(self) -> bool:
        """
         Initialize database. This is called before any operations are performed to ensure database is up to date. If you don't want to do this call : meth : ` ~pyflink. table. Table. create_db ` instead.


         @return True if database has been initialized False otherwise. Note that it's possible that the database could not be initialized
        """
        raise NotImplementedError

    @abstractmethod
    def buckets(self) -> Dict[str, dict]:
        """
         Return a dictionary of bucket names and values. This is useful for debugging the user's experience with an unusual number of buckets per project.


         @return A dictionary of bucket names and values keyed by project name ( str ) and with values as dictionaries of buckets
        """
        raise NotImplementedError

    @abstractmethod
    def create_bucket(
            self,
            bucket_id: str,
            type_id: str,
            client: str,
            hostname: str,
            created: str,
            name: Optional[str] = None,
            data: Optional[dict] = None,
    ) -> None:
        """
         Creates a bucket. This is a non - blocking call and will return immediately. The bucket must be in the ACTIVE state before it can be created.

         @param bucket_id - The ID of the bucket to create.
         @param type_id - The type of the bucket as defined in S3.
         @param client - The client that is making the request. If you don't specify a client the default client will be used.
         @param hostname - The hostname of the bucket. This is used to generate a unique name for the bucket and can be used to retrieve it later by calling
         @param created - The time at which the bucket was created.
         @param name - The name of the bucket. If not specified one will be generated.
         @param data - The data to send with the bucket. It can be a dict or a list of dicts.

         @return True if the bucket was created False otherwise. note :: You must have WRITE permission to the bucket to create it
        """
        raise NotImplementedError

    @abstractmethod
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
         Updates an existing bucket. You must provide at least one of the parameters. Required Permissions ** : To use this action an IAM user must have a Manage permissions level for the stack or an attached policy that explicitly grants permissions. For more information on user permissions see ` Managing User Permissions ` _.

         @param bucket_id - The ID of the bucket to update.
         @param type_id - The type of the bucket ( bucket or policy ) that is being operated on.
         @param client - The client to use for this request. If not specified the default client is used.
         @param hostname - The hostname of the bucket. If not specified the default hostname is used.
         @param name - The name of the bucket. If not specified the default name is used.
         @param data - The data to be stored in the bucket.

         @return The response to the request. code - block :: python import paddle from pywbem. pool import Bucket >>> client = paddle. client. Bucket ( " my - bucket " ) >>> res = paddle. client
        """
        raise NotImplementedError

    @abstractmethod
    def delete_bucket(self, bucket_id: str) -> None:
        """
         Deletes a bucket. This is a no - op if the bucket does not exist. It returns a deferred that fires when the bucket is deleted.

         @param bucket_id - The ID of the bucket to delete.

         @return An instance of no - op CloudStorageResponse. BucketDeleted is returned on success. Otherwise None is returned
        """
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, bucket_id: str) -> dict:
        """
         Get metadata for a bucket. This is a no - op in this backend. You should override this if you want to do something other than return a dictionary of key / value pairs that are relevant to the bucket.

         @param bucket_id - The ID of the bucket to get metadata for.

         @return A dictionary of key / value pairs that are relevant to the bucket. Keys are strings and values are lists
        """
        raise NotImplementedError

    @abstractmethod
    def get_event(
            self,
            bucket_id: str,
            event_id: int,
    ) -> Optional[Event]:
        """
         Retrieves an event by bucket and event id. This is a low - level method that should be implemented by subclasses.

         @param bucket_id - The ID of the bucket to retrieve the event from.
         @param event_id - The ID of the event to retrieve.

         @return The event or None if not found. Raises : class : ` ~google. cloud. storage. v1_5. errors. ResourceNotFound ` if the bucket does not exist
        """
        raise NotImplementedError

    @abstractmethod
    def get_events(
            self,
            bucket_id: str,
            limit: int,
            starttime: Optional[datetime] = None,
            endtime: Optional[datetime] = None,
    ) -> List[Event]:
        """
         Get events from a bucket. This is a low - level method that should be used by clients to query the events in a bucket.

         @param bucket_id - The bucket to query. Must be a string that uniquely identifies a bucket.
         @param limit - The maximum number of events to return. If this is less than the number of events returned an empty list is returned.
         @param starttime - The start time of the time range to query. Defaults to the current time.
         @param endtime - The end time of the time range to query. Defaults to the current time.

         @return A list of : class : ` ~google. cloud. bigquery. event. Event ` objects
        """
        raise NotImplementedError

    def get_eventcount(
            self,
            bucket_id: str,
            starttime: Optional[datetime] = None,
            endtime: Optional[datetime] = None,
    ) -> int:
        """
         Get the number of events in a bucket. This is a low - level method that should be implemented by subclasses.

         @param bucket_id - The bucket to query. Must be a string that uniquely identifies a bucket.
         @param starttime - The start time of the time range in UTC. If not specified the current time is used. ( Default : None )
         @param endtime - The end time of the time range in UTC. If not specified the current time is used. ( Default : None )

         @return The number of events in the bucket between starttime and endtime. If no time range is specified the current time is used
        """
        raise NotImplementedError

    @abstractmethod
    def insert_one(self, bucket_id: str, event: Event) -> Event:
        """
         Insert a single event into the storage. This is the method to be implemented by subclasses. The bucket_id must be the same as the bucket used to store the event

         @param bucket_id - The id of the bucket
         @param event - The event to be stored

         @return The event that was stored or None if there was no event for the bucket_id ( in which case the event will be returned
        """
        raise NotImplementedError

    def insert_many(self, bucket_id: str, events: List[Event]) -> None:
        """
         Insert multiple events into a bucket. This is a convenience method for insert_one ( bucket_id event )

         @param bucket_id - The bucket to insert into
         @param events - A list of events to insert into the bucket

         @return True if successful False if there was an error ( in which case the exception will be propogated
        """
        # Insert one or more events into the bucket.
        for event in events:
            self.insert_one(bucket_id, event)

    @abstractmethod
    def delete(self, bucket_id: str, event_id: int) -> bool:
        """
         Delete an event from Google Cloud Storage. This is an asynchronous operation. To check if the event has been deleted call

         @param bucket_id - Id of bucket to delete from
         @param event_id - Id of event to delete from bucket

         @return True if deleted False if not ( error will be raised in bucket_id event_id or bucket
        """
        raise NotImplementedError

    @abstractmethod
    def replace(self, bucket_id: str, event_id: int, event: Event) -> bool:
        """
         Replaces an event in a bucket. This is a no - op if the bucket does not exist.

         @param bucket_id - The ID of the bucket to replace the event in.
         @param event_id - The ID of the event to replace.
         @param event - The event to replace. Must be serializable if serializable.

         @return True if the operation succeeded False otherwise. >>> client. replace ('abc'' bishop '
        """
        raise NotImplementedError

    @abstractmethod
    def replace_last(self, bucket_id: str, event: Event) -> None:
        """
         Replaces the last event in a bucket. This is a no - op if there is no event to replace

         @param bucket_id - The bucket where the event is stored
         @param event - The event to replace the last event in the bucket

         @return True if the replace was successful False if it wasn't ( or was not possible for some reason
        """
        raise NotImplementedError

    @abstractmethod
    def save_settings(self, code, value) -> None:
        """
         Save settings to the storage. This is called by : meth : ` ~settings_store ` to allow the user to save a set of settings for an object or a set of objects that are stored in the storage.

         @param settings_id - The ID of the settings to save.
         @param settings_dict - A dictionary of settings to save.

         @return True if the settings were saved False otherwise. If a value is returned it will be returned as the result of the call
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve_settings(self, code) -> dict:
        """
         Retrieve settings from the storage. This is a low - level method that should be implemented by sub - classes.

         @param settings_id - ID of the settings to retrieve.

         @return Dictionary of settings or None if not found. Note that the keys are strings and the values are dictionaries
        """
        raise NotImplementedError

    def save_application_details(self, application_details):
        raise NotImplementedError

    def retrieve_application_details(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_most_used_apps(self, starttime, endtime) -> []:
        """
         Get a list of apps that have been used in the time range. This is useful for debugging and to see what apps need to be installed on the system

         @param starttime - start time of the time range
         @param endtime - end time of the time range ( inclusive )

         @return list of app objects sorted by time ( oldest to newest ) in chronological order and with the most used apps
        """
        raise NotImplementedError

    @abstractmethod
    def get_dashboard_events(self, starttime, endtime) -> []:
        """
         Get dashboard events. This is a generator that yields the dashboard events that occur between the start and end times.

         @param starttime - The start time of the time range to query.
         @param endtime - The end time of the time range to query.

         @return A list of : class : ` DashboardEvent ` objects one for each event in the time range. If there are no events the list will be empty
        """
        raise NotImplementedError

    @abstractmethod
    def get_non_sync_events(self) -> []:
        raise NotImplementedError

    @abstractmethod
    def update_server_sync_status(self, list_of_ids, new_status):
        raise NotImplementedError
