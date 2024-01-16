import logging
from typing import List, Dict, Tuple

from aw_core.models import Event

logger = logging.getLogger(__name__)


def merge_events_by_keys(events, keys) -> List[Event]:
    """
     Merge events by keys. This is a recursive function to merge a list of events into a single list of events based on the key ( s ) that have been consumed
     
     @param events - List of events to be merged
     @param keys - List of keys to be consumed by the merge
     
     @return List of events with merged keys from the input list of events ( in order ) Note : Events are returned as a
    """
    # Call recursively until all keys are consumed
    # Return events for the first key.
    if len(keys) < 1:
        return events
    merged_events: Dict[Tuple, Event] = {}
    # Merge events into a new Event object.
    for event in events:
        composite_key: Tuple = ()
        # Returns a composite key for each key in the event data.
        for key in keys:
            # This function is used to add a composite key to the event data.
            if key in event.data:
                val = event["data"][key]
                # Needed for when the value is a list, such as for categories
                # Convert a list or tuple to a tuple.
                if isinstance(val, list):
                    val = tuple(val)
                composite_key = composite_key + (val,)
        # Merge events with the same data.
        if composite_key not in merged_events:
            merged_events[composite_key] = Event(
                timestamp=event.timestamp, duration=event.duration, data={}
            )
            # Merge events with merged events.
            for key in keys:
                # Merge event data with composite key
                if key in event.data:
                    merged_events[composite_key].data[key] = event.data[key]
        else:
            merged_events[composite_key].duration += event.duration
    result = []
    # Add merged events to result.
    for key in merged_events:
        result.append(Event(**merged_events[key]))
    return result
