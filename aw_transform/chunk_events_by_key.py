import logging
from datetime import timedelta
from typing import List

from aw_core.models import Event

logger = logging.getLogger(__name__)


def chunk_events_by_key(
    events: List[Event], key: str, pulsetime: float = 5.0
) -> List[Event]:
    """
     Chunk events by key. This is useful for keeping track of events that have different values for a key and are in the same subevent ( s )
     
     @param events - List of events to chunk
     @param key - Key to chunk by default is " timestamp "
     @param pulsetime - Time in seconds to use for chunking
     
     @return List of events with chunked data in the " subevents " key of the new event. The list is sorted by
    """
    chunked_events: List[Event] = []
    for event in events:
        if key not in event.data:
            break
        timediff = timedelta(seconds=999999999)  # FIXME: ugly but works
        # This function will iterate over all events in the list and add them to the list of events.
        if len(chunked_events) > 0:
            # Check if the key is in event. data
            timediff = event.timestamp - (events[-1].timestamp + events[-1].duration)
        if (
            len(chunked_events) > 0
            # Calculate the time difference between the chunked events.
            and chunked_events[-1].data[key] == event.data[key]
            and timediff < timedelta(seconds=pulsetime)
        # Add a new chunked event to the list of events.
        ):
            chunked_event = chunked_events[-1]
            chunked_event.duration += event.duration
            chunked_event.data["subevents"].append(event)
        else:
            data = {key: event.data[key], "subevents": [event]}
            chunked_event = Event(
                timestamp=event.timestamp, duration=event.duration, data=data
            )
            chunked_events.append(chunked_event)

    return chunked_events
