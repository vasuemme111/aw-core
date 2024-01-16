import logging
from datetime import timedelta
from typing import List, Optional

from aw_core.models import Event

logger = logging.getLogger(__name__)


def heartbeat_reduce(events: List[Event], pulsetime: float) -> List[Event]:
    """
     Heartbeats are merged with the last event. This is a wrapper around heartbeat_merge that does not check for duplicates
     
     @param events - List of events to reduce
     @param pulsetime - Time in seconds to use for merge
     
     @return A list of events that were merged with the last event in the list and have the same pulset
    """
    reduced = []
    # Add the last event to the reduced list.
    if events:
        reduced.append(events.pop(0))
    # Merge heartbeat events with the same heartbeat.
    for heartbeat in events:
        merged = heartbeat_merge(reduced[-1], heartbeat, pulsetime)
        # Add a heartbeat to the reduced list of heartbeat.
        if merged is not None:
            # Heartbeat was merged
            reduced[-1] = merged
        else:
            # Heartbeat was not merged
            reduced.append(heartbeat)
    return reduced


def heartbeat_merge(
    last_event: Event, heartbeat: Event, pulsetime: float
) -> Optional[Event]:
    """
     Merge two heartbeats into a single event. This is used to determine if the heartbeat is indempotent and if so how long it should be.
     
     @param last_event - The event that was the last heartbeat
     @param heartbeat - The event that we want to merge
     @param pulsetime - The pulse time in seconds for the heartbeat
     
     @return The merged event or None if there was no merge to be done ( in which case the last event is returned
    """
    # The last event that was last_event. data heartbeat. data heartbeat. data heartbeat. data heartbeat. data heartbeat. data heartbeat. data
    if last_event.data == heartbeat.data:
        # Seconds between end of last_event and start of heartbeat
        pulseperiod_end = (
            last_event.timestamp + last_event.duration + timedelta(seconds=pulsetime)
        )
        within_pulsetime_window = (
            last_event.timestamp <= heartbeat.timestamp <= pulseperiod_end
        )

        # Returns the last event that was last_event.
        if within_pulsetime_window:
            # Seconds between end of last_event and start of timestamp
            new_duration = (
                heartbeat.timestamp - last_event.timestamp
            ) + heartbeat.duration
            # Returns the last event that was last_event.
            if last_event.duration < timedelta(0):
                logger.warning(
                    "Merging heartbeats would result in a negative duration, refusing to merge."
                )
            else:
                # Taking the max of durations ensures heartbeats that end before the last event don't shorten it
                last_event.duration = max((last_event.duration, new_duration))
                return last_event

    return None
