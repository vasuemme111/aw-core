import logging
from typing import List

from urllib.parse import urlparse

from aw_core.models import Event

logger = logging.getLogger(__name__)


def split_url_events(events: List[Event]) -> List[Event]:
    """
     Split events that have a url attribute into a list of events. This is used to make sure that events are sent to Sensu in the right order and have the correct data
     
     @param events - A list of events to split
     
     @return A list of events with url attributes split into events that have a url attribute ( if present ) and
    """
    # This function will parse the event data and return the event data.
    for event in events:
        # Event data is a dictionary of event data.
        if "url" in event.data:
            url = event.data["url"]
            parsed_url = urlparse(url)
            event.data["$protocol"] = parsed_url.scheme
            event.data["$domain"] = (
                parsed_url.netloc[4:]
                if parsed_url.netloc[:4] == "www."
                else parsed_url.netloc
            )
            event.data["$path"] = parsed_url.path
            event.data["$params"] = parsed_url.params
            event.data["$options"] = parsed_url.query
            event.data["$identifier"] = parsed_url.fragment
            # TODO: Parse user, port etc aswell
    return events
