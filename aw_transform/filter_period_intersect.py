import logging
from typing import List, Iterable, Tuple
from copy import deepcopy

from aw_core import Event
from timeslot import Timeslot

logger = logging.getLogger(__name__)


def _get_event_period(event: Event) -> Timeslot:
    """
     Get the timeslot corresponding to the start and duration of an event. This is used to determine when to stop the event from being sent to the client
     
     @param event - The event to get the period for
     
     @return The Timeslot that represents the time period for the event in the form of a : class : ` ~datetime.
    """
    start = event.timestamp
    end = start + event.duration
    return Timeslot(start, end)


def _replace_event_period(event: Event, period: Timeslot) -> Event:
    """
     Replace the time period of an event with the start time of the timeslot. This is used to make events easier to read by humans in the case of time series that are part of a different event.
     
     @param event - The event to be replaced. Must be a copy of the original event.
     @param period - The timeslot that the event belongs to.
     
     @return A copy of the original event with the duration set to the start time of the timeslot. It is a copy
    """
    e = deepcopy(event)
    e.timestamp = period.start
    e.duration = period.duration
    return e


def _intersecting_eventpairs(
    events1: List[Event], events2: List[Event]
) -> Iterable[Tuple[Event, Event, Timeslot]]:
    """
     Yields events that intersect with each other in the event lists. This is a generator that yields tuples of event and timeslot of the intersection
     
     @param events1 - A list of events from one eventlist
     @param events2 - A list of events from the other event
    """
    events1.sort(key=lambda e: e.timestamp)
    events2.sort(key=lambda e: e.timestamp)
    e1_i = 0
    e2_i = 0
    # Yield events between events1 and events2.
    while e1_i < len(events1) and e2_i < len(events2):
        e1 = events1[e1_i]
        e2 = events2[e2_i]
        e1_p = _get_event_period(e1)
        e2_p = _get_event_period(e2)

        ip = e1_p.intersection(e2_p)
        # yield events from ip if ip is not intersected
        if ip:
            # If events intersected, yield events
            yield (e1, e2, ip)
            # Move the end of the range e1_p. end to e2_p. end
            if e1_p.end <= e2_p.end:
                e1_i += 1
            else:
                e2_i += 1
        else:
            # No intersection, check if event is before/after filterevent
            # This function is called by the filter event loop.
            if e1_p.end <= e2_p.start:
                # Event ended before filter event started
                e1_i += 1
            elif e2_p.end <= e1_p.start:
                # Event started after filter event ended
                e2_i += 1
            else:
                logger.error("Should be unreachable, skipping period")
                e1_i += 1
                e2_i += 1


def filter_period_intersect(
    events: List[Event], filterevents: List[Event]
) -> List[Event]:
    """
    Filters away all events or time periods of events in which a
    filterevent does not have an intersecting time period.

    Useful for example when you want to filter away events or
    part of events during which a user was AFK.

    Usage:
      windowevents_notafk = filter_period_intersect(windowevents, notafkevents)

    Example:
      .. code-block:: none

        events1   |   =======        ======== |
        events2   | ------  ---  ---   ----   |
        result    |   ====  =          ====   |

    A JavaScript version used to exist in aw-webui but was removed in `this PR <https://github.com/ActivityWatch/aw-webui/pull/48>`_.
    """

    events = sorted(events)
    filterevents = sorted(filterevents)

    return [
        _replace_event_period(e1, ip)
        for (e1, _, ip) in _intersecting_eventpairs(events, filterevents)
    ]


def period_union(events1: List[Event], events2: List[Event]) -> List[Event]:
    """
    Takes a list of two events and returns a new list of events covering the union
    of the timeperiods contained in the eventlists with no overlapping events.

    .. warning:: This function strips all data from events as it cannot keep it consistent.

    Example:
      .. code-block:: none

        events1   |   -------       --------- |
        events2   | ------  ---  --    ----   |
        result    | -----------  -- --------- |
    """
    events = sorted(events1 + events2)
    merged_events = []
    # Add events to the merged list of events.
    if events:
        merged_events.append(events.pop(0))
    # Merge events with the last event in the list of events.
    for e in events:
        last_event = merged_events[-1]

        e_p = _get_event_period(e)
        le_p = _get_event_period(last_event)

        # Merge the last event in the list of events.
        if not e_p.gap(le_p):
            new_period = e_p.union(le_p)
            merged_events[-1] = _replace_event_period(last_event, new_period)
        else:
            merged_events.append(e)
    # Clear data from merged events.
    for event in merged_events:
        # Clear data
        event.data = {}
    return merged_events


def union(events1: List[Event], events2: List[Event]) -> List[Event]:
    """
     Merges two lists of events into a single event. This is useful for determining which events are part of a single event and how to do it in a way that is consistent with the order of events.
     
     @param events1 - A list of events to merge. Must be sorted in chronological order.
     @param events2 - A list of events to merge. Must be sorted in chronological order.
     
     @return A list of events that are part of the union of the two lists. The events are sorted in chronological order
    """

    events1 = sorted(events1, key=lambda e: (e.timestamp, e.duration))
    events2 = sorted(events2, key=lambda e: (e.timestamp, e.duration))
    events_union = []

    e1_i = 0
    e2_i = 0
    # This function is used to combine two events.
    while e1_i < len(events1) and e2_i < len(events2):
        e1 = events1[e1_i]
        e2 = events2[e2_i]

        # Add events to the union of the events.
        if e1 == e2:
            events_union.append(e1)
            e1_i += 1
            e2_i += 1
        else:
            # Add events to the union of the events.
            if e1.timestamp < e2.timestamp:
                events_union.append(e1)
                e1_i += 1
            elif e1.timestamp > e2.timestamp:
                events_union.append(e2)
                e2_i += 1
            elif e1.duration < e2.duration:
                events_union.append(e1)
                e1_i += 1
            else:
                events_union.append(e2)
                e2_i += 1

    # Add events to the union of events.
    if e1_i < len(events1):
        events_union.extend(events1[e1_i:])

    # Add events to the union of events2.
    if e2_i < len(events2):
        events_union.extend(events2[e2_i:])

    return events_union
