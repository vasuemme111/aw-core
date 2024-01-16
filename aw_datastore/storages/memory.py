import copy
import sys
from datetime import datetime
from typing import Dict, List, Optional

from aw_core.models import Event

from . import logger
from .abstract import AbstractStorage


class MemoryStorage(AbstractStorage):
    """For storage of data in-memory, useful primarily in testing"""

    sid = "memory"

    def __init__(self, testing: bool) -> None:
        """
         Initialize the object. This is called by __init__ and should not be called directly. You should not need to call this yourself.
         
         @param testing - If True use test mode. Default is
        """
        self.logger = logger.getChild(self.sid)
        # self.logger.warning("Using in-memory storage, any events stored will not be persistent and will be lost when server is shut down. Use the --storage parameter to set a different storage method.")
        self.db: Dict[str, List[Event]] = {}
        self._metadata: Dict[str, dict] = dict()

    def create_bucket(
        self,
        bucket_id,
        type_id,
        client,
        hostname,
        created,
        name=None,
        data=None,
    ) -> None:
        """
         Create a bucket in the bucket store. This is a low - level method to be used by clients that want to create buckets in different ways.
         
         @param bucket_id - The ID of the bucket to create.
         @param type_id - The type of the bucket ( bucket_type ).
         @param client - The client that created the bucket. This can be any value that can be cast to a string or a : class : ` ~google. cloud.
         @param hostname
         @param created
         @param name
         @param data
        """
        # Set the name of the bucket.
        if not name:
            name = bucket_id
        self._metadata[bucket_id] = {
            "id": bucket_id,
            "name": name,
            "type": type_id,
            "client": client,
            "hostname": hostname,
            "created": created,
            "data": data or {},
        }
        self.db[bucket_id] = []

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
         Update bucket metadata. This will update the bucket's type hostname name and / or data if it exists
         
         @param bucket_id - The ID of the bucket to update
         @param type_id - The type of the bucket ( bucket / bucket - group )
         @param client - The client to use for this bucket ( default : None )
         @param hostname - The hostname to use for this bucket ( default : None )
         @param name - The name to use for this bucket ( default : None )
         @param data - The data to update the bucket with ( default : None )
         
         @return True if success False if not ( exception will be raised if bucket does not exist in this bucket )
        """
        # Update the bucket metadata.
        if bucket_id in self._metadata:
            # Set the type of the bucket
            if type_id:
                self._metadata[bucket_id]["type"] = type_id
            # Set the client to use for this bucket
            if client:
                self._metadata[bucket_id]["client"] = client
            # Set the hostname of the bucket
            if hostname:
                self._metadata[bucket_id]["hostname"] = hostname
            # Set the name of the bucket
            if name:
                self._metadata[bucket_id]["name"] = name
            # Set the data of the bucket
            if data:
                self._metadata[bucket_id]["data"] = data
        else:
            raise Exception("Bucket did not exist, could not update")

    def delete_bucket(self, bucket_id: str) -> None:
        """
         Delete a bucket from the storage. This is useful for testing the ability to delete buckets that are no longer used
         
         @param bucket_id - The id of the bucket to delete
         
         @return True if the bucket was deleted False if it didn't exist or could not be deleted due to
        """
        # Remove the bucket from the database.
        if bucket_id in self.db:
            del self.db[bucket_id]
        # Delete the bucket from the metadata
        if bucket_id in self._metadata:
            del self._metadata[bucket_id]
        else:
            raise Exception("Bucket did not exist, could not delete")

    def buckets(self):
        """
         Get all buckets in the database. This is a dict keyed by bucket id with values being the metadata of the bucket.
         
         
         @return A dict keyed by bucket id with values being the metadata of the bucket or None if there is no
        """
        buckets = dict()
        # Add metadata for each bucket to the database.
        for bucket_id in self.db:
            buckets[bucket_id] = self.get_metadata(bucket_id)
        return buckets

    def get_event(
        self,
        bucket_id: str,
        event_id: int,
    ) -> Optional[Event]:
        """
         Get an event by bucket and event id. This is a low - level method that should be used when you want to retrieve a specific event from the event store.
         
         @param bucket_id - The id of the bucket to retrieve the event from.
         @param event_id - The id of the event to retrieve.
         
         @return The event or None if not found. Note that the event may be in the process of being deleted
        """
        event = self._get_event(bucket_id, event_id)
        return copy.deepcopy(event)

    def get_events(
        self,
        bucket: str,
        limit: int,
        starttime: Optional[datetime] = None,
        endtime: Optional[datetime] = None,
    ) -> List[Event]:
        """
         Get events from a bucket. This is a low - level method to use when you want to get a list of events from the database.
         
         @param bucket - The bucket to query. Must be a string that contains at least one key " events "
         @param limit - The maximum number of events to return.
         @param starttime
         @param endtime
        """
        events = self.db[bucket]

        # Sort by timestamp
        events = sorted(events, key=lambda k: k["timestamp"])[::-1]

        # Filter by date
        # Returns a list of events that are within the given timestamp and duration.
        if starttime:
            events = [e for e in events if starttime <= (e.timestamp + e.duration)]
        # Removes events that are older than endtime.
        if endtime:
            events = [e for e in events if e.timestamp <= endtime]

        # Limit
        # limit is the maximum number of results to return.
        if limit == 0:
            return []
        elif limit < 0:
            limit = sys.maxsize
        events = events[:limit]
        # Return
        return copy.deepcopy(events)

    def get_eventcount(
        self,
        bucket: str,
        starttime: Optional[datetime] = None,
        endtime: Optional[datetime] = None,
    ) -> int:
        """
         Get the number of events in a bucket. This is useful for determining how many events have been added since the start of the call to : meth : ` add_event `.
         
         @param bucket - The name of the bucket to query. Must be a fully - qualified name e. g.
         @param starttime - The start time of the event in UTC seconds since the epoch ( defaults to now ).
         @param endtime - The end time of the event in UTC seconds since the epoch ( defaults to now ).
         
         @return The number of events in the bucket between starttime and endtime ( defaults to None ). Note that the bucket may be empty
        """
        return len(
            [
                e
                for e in self.db[bucket]
                if (not starttime or starttime <= e.timestamp)
                and (not endtime or e.timestamp <= endtime)
            ]
        )

    def get_metadata(self, bucket_id: str):
        """
         Get metadata associated with a bucket. This is useful for obtaining information about an object such as a bucket's metadata.
         
         @param bucket_id - The ID of the bucket to get metadata for.
         
         @return A dictionary of key / value pairs that describe the metadata associated with the bucket or None if no metadata is associated
        """
        # Returns the metadata for the given bucket.
        if bucket_id in self._metadata:
            return self._metadata[bucket_id]
        else:
            raise Exception("Bucket did not exist, could not get metadata")

    def insert_one(self, bucket: str, event: Event) -> Event:
        """
         Insert a single event into the database. If the event has an ID it will be replaced otherwise a new ID will be generated
         
         @param bucket - The bucket to insert the event into
         @param event - The event to insert into the database. This is a copy of the event
         
         @return The event that was
        """
        # Replace the event with the event.
        if event.id is not None:
            self.replace(bucket, event.id, event)
        else:
            # We need to copy the event to avoid setting the ID on the passed event
            event = copy.copy(event)
            # Get the event id for the bucket
            if self.db[bucket]:
                event.id = max(int(e.id or 0) for e in self.db[bucket]) + 1
            else:
                event.id = 0
            self.db[bucket].append(event)
        return event

    def delete(self, bucket_id, event_id):
        """
         Delete an event from the database. This is useful for deleting events that don't have a reference to them.
         
         @param bucket_id - The bucket to search for the event.
         @param event_id - The id of the event to delete.
         
         @return True if the event was found and deleted False otherwise. Note that it is possible that there are multiple events with the same id
        """
        # Remove the event from the bucket.
        for idx in (
            idx
            for idx, event in reversed(list(enumerate(self.db[bucket_id])))
            if event.id == event_id
        ):
            self.db[bucket_id].pop(idx)
            return True
        return False

    def _get_event(self, bucket_id, event_id) -> Optional[Event]:
        """
         Get an event from the database. This is used to get a specific event by ID. If there is more than one event with the given ID None is returned
         
         @param bucket_id - The ID of the bucket to search
         @param event_id - The ID of the event to search for
         
         @return The event or None if not found ( in which case None is returned to indicate that no event was found
        """
        events = [
            event
            for idx, event in reversed(list(enumerate(self.db[bucket_id])))
            if event.id == event_id
        ]
        # Return the first event in the list.
        if len(events) < 1:
            return None
        else:
            return events[0]

    def replace(self, bucket_id, event_id, event):
        """
         Replaces an event with a new one. This is useful for events that have been removed from the database before the event was added.
         
         @param bucket_id - The bucket to search for the event
         @param event_id - The ID of the event to replace
         @param event - The event to replace the ID of the event
        """
        # Copy the event to the event_id
        for idx in (
            idx
            for idx, event in reversed(list(enumerate(self.db[bucket_id])))
            if event.id == event_id
        ):
            # We need to copy the event to avoid setting the ID on the passed event
            event = copy.copy(event)
            event.id = event_id
            self.db[bucket_id][idx] = event

    def replace_last(self, bucket_id, event):
        """
         Replaces the last event in a bucket with the given event. This is useful when you want to replace the most frequent event in a bucket.
         
         @param bucket_id - The id of the bucket to replace the event in
         @param event - The event to replace
        """
        # NOTE: This does not actually get the most recent event, only the last inserted
        last = sorted(self.db[bucket_id], key=lambda e: e.timestamp)[-1]
        self.replace(bucket_id, last.id, event)
