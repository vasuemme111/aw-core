import json
import logging
import numbers
import typing
from datetime import datetime, timedelta, timezone
from typing import (
    Any,
    Dict,
    Optional,
    Union,
)
import re
import iso8601
from tldextract import tldextract

logger = logging.getLogger(__name__)

Number = Union[int, float]
Id = Optional[Union[int, str]]
ConvertibleTimestamp = Union[datetime, str]
Duration = Union[timedelta, Number]
Data = Dict[str, Any]
app = str
title = str
url = str
application_name=str
server_sync_status = Number


def _timestamp_parse(ts_in: ConvertibleTimestamp) -> datetime:
    """
     Parses a timestamp and returns a datetime object. This is a helper function for : func : ` _timestamp_from_iso8601 `

     @param ts_in - The timestamp to parse.

     @return A datetime object representing the timestamp in the format used by : func : ` _timestamp_from_iso8601
    """
    ts = iso8601.parse_date(ts_in) if isinstance(ts_in, str) else ts_in
    # Set resolution to milliseconds instead of microseconds
    # (Fixes incompability with software based on unix time, for example mongodb)
    ts = ts.replace(microsecond=int(ts.microsecond / 1000) * 1000)
    # Add timezone if not set
    # Returns a copy of the timestamp with timezone set to UTC.
    if not ts.tzinfo:
        # Needed? All timestamps should be iso8601 so ought to always contain timezone.
        # Yes, because it is optional in iso8601
        logger.warning(f"timestamp without timezone found, using UTC: {ts}")
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


class Event(dict):
    """
    Used to represents an event.
    """

    def __eq__(self, other: object) -> bool:
        """
         Compare two : class : ` Event ` for equality. This is used to implement __eq__ as part of the equality operator and should not be used in general.

         @param other - The object to compare with. It must be an instance of : class : ` Event `.

         @return True if equal False otherwise. >>> event. __eq__ ( event ) Traceback ( most recent call last ) : TypeError : operator not supported between instances of
        """
        # Returns True if the two events are equal.
        if isinstance(other, Event):
            return (
                    self.timestamp == other.timestamp
                    and self.duration == other.duration
                    and self.data == other.data
            )
        else:
            raise TypeError(
                "operator not supported between instances of '{}' and '{}'".format(
                    type(self), type(other)
                )
            )

    def __init__(
            self,
            id: Optional[Id] = None,
            timestamp: Optional[ConvertibleTimestamp] = None,
            duration: Duration = 0,
            data: Data = dict(),
            app: app = '',
            title: title = '',
            url: url = '',
            application_name: application_name = '',
            server_sync_status: server_sync_status = 0
    ) -> None:
        """
         Initialize an event with the given id timestamp duration and data. This is the constructor for Event objects that do not need to be called directly.

         @param id - The id of the event. If None the id will be set to the current time.
         @param timestamp - The timestamp to use for the event. If None the timestamp will be set to the current time.
         @param duration - The duration of the event in seconds. Default is 0.
         @param data - The data associated with the event. Default is an empty dictionary.

         @return A reference to the newly created Event object for convenience / error handling purposes. Note that the event is not saved
        """
        self.id = id
        # Initialize the event initializer with a timestamp.
        if timestamp is None:
            logger.warning(
                "Event initializer did not receive a timestamp argument, "
                "using now as timestamp"
            )
            # FIXME: The typing.cast here was required for mypy to shut up, weird...
            self.timestamp = datetime.now(typing.cast(timezone, timezone.utc))
        else:
            # The conversion needs to be explicit here for mypy to pick it up
            # (lacks support for properties)
            self.timestamp = _timestamp_parse(timestamp)
        self.duration = duration  # type: ignore
        self.data = data
        self.app = data.get('app', '')
        self.title = data.get('title', '')
        self.url = data.get('url', '')
        if not self.url:
            app_name = self.app
        else:
            app_name = tldextract.extract(self.url).domain
        if not app_name:
            app_name = self.app
        if ".exe" in app_name.lower():
            app_name = re.sub(r'\.exe$', '', app_name)
        self.application_name = app_name
        self.server_sync_status = server_sync_status

    def __lt__(self, other: object) -> bool:
        """
         Compare two : class : ` Event ` objects based on their timestamp. This is equivalent to the less than operator in Python.

         @param other - The other object to compare. Must be an : class : ` Event ` instance.

         @return True if self < other False otherwise. >>> event. __lt__ ( event ) Traceback ( most recent call last ) : TypeError : not supported between instances of
        """
        # Returns True if this operator is less than other.
        if isinstance(other, Event):
            return self.timestamp < other.timestamp
        else:
            raise TypeError(
                "operator not supported between instances of '{}' and '{}'".format(
                    type(self), type(other)
                )
            )

    def to_json_dict(self) -> dict:
        """
         Convert to a dict that can be used for sending to the wire. Anything that needs to be serialized is copied to the output.


         @return A dict with timestamp and duration in ISO 8601 format and total seconds in the format of : class : ` datetime. datetime
        """
        """Useful when sending data over the wire.
        Any mongodb interop should not use do this as it accepts datetimes."""
        json_data = self.copy()
        json_data["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        json_data["duration"] = self.duration.total_seconds()
        return json_data

    def to_json_str(self) -> str:
        """
         Convert to JSON string. This is useful for debugging and to get a human readable string of the object's data.


         @return The object's data in JSON format as a string. Example :. from pants. python import pants_
        """
        data = self.to_json_dict()
        return json.dumps(data)

    def _hasprop(self, propname: str) -> bool:
        """
         Check if the underlying dict has a property. This is a helper for __getitem__ and __setitem__ to avoid having to reimplement it

         @param propname - Name of the property to check

         @return True if the property exists and is not None False if it does not exist or isn't a non - empty
        """
        """Badly named, but basically checks if the underlying
        dict has a prop, and if it is a non-empty list"""
        return propname in self and self[propname] is not None

    @property
    def id(self) -> Id:
        """
         The ID of the entity. This is used to distinguish entities from other entities in the same request.


         @return The entity's ID or None if not present in the request or if it has no ID set
        """
        return self["id"] if self._hasprop("id") else None

    @id.setter
    def id(self, id: Id) -> None:
        """
         The id of the resource. It can be a string or integer. Defaults to : py : attr : ` id `.


         @return The current instance of : py : class : ` Resource `. >>> from owlmixin. res. resource import Resource >>> from owlmixin. res. resource
        """
        self["id"] = id

    @property
    def data(self) -> dict:
        """
         The data associated with this event. If not set a default data will be used. This is useful for debugging purposes and to ensure that events are displayed in the correct order when they are generated.


         @return ` dict ` of data or ` {} ` if not set in the W3C Data API ( See
        """
        return self["data"] if self._hasprop("data") else {}

    @data.setter
    def data(self, data: dict) -> None:
        """
         The data of the chart. Must be a dictionary with keys corresponding to the columns in the chart.


         @return The current chart object. Example. code - block :: python import plotly. chart as chart >>> chart. chart ( chart. data ) Traceback ( most recent call last ) : ValueError : Cannot set data to None
        """
        self["data"] = data

    @property
    def timestamp(self) -> datetime:
        """
         Sets the timestamp of the plotly. graph_objs. layout. template. data. Time object. If set to a string it must be parsable as a date string. The'timestamp'property is a string and must be specified as : A string A number that will be converted to a date string Returns


         @return The'timestamp'property of this Plotly. graph_objs. layout. data. Time object
        """
        return self["timestamp"]

    @timestamp.setter
    def timestamp(self, timestamp: ConvertibleTimestamp) -> None:
        """
         The timestamp to set. If omitted defaults to the current time. : param timestamp : The timestamp to set
        """
        self["timestamp"] = _timestamp_parse(timestamp).astimezone(timezone.utc)

    @property
    def duration(self) -> timedelta:
        """
         Union [ timedelta None ] : Duration of the time series. If not specified defaults to 0 seconds.


         @return The duration of the time series ( timedelta ) or 0 if not specified in the JSON or if not
        """
        return self["duration"] if self._hasprop("duration") else timedelta(0)

    @duration.setter
    def duration(self, duration: Duration) -> None:
        """
         The duration of the job. Can be a : class : ` ~datetime. timedelta ` or a number of seconds since January 1 1970.


         @return The duration of the job in seconds ( None if not set ). >>> job. duration ( 10 ) Traceback ( most recent call last ) : TypeError : Couldn't parse duration
        """
        # duration is a number of seconds or seconds. Real or numbers. Real.
        if isinstance(duration, timedelta):
            self["duration"] = duration
        elif isinstance(duration, numbers.Real):
            self["duration"] = timedelta(seconds=duration)  # type: ignore
        else:
            raise TypeError(f"Couldn't parse duration of invalid type {type(duration)}")

    @property
    def server_sync_status(self) -> None:
        return self["server_sync_status"]

    @server_sync_status.setter
    def server_sync_status(self, server_sync_status: Number) -> None:
        self["server_sync_status"] = server_sync_status
