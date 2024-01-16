import logging
from typing import List
import re

from aw_core.models import Event

logger = logging.getLogger(__name__)


def filter_keyvals(
    events: List[Event], key: str, vals: List[str], exclude=False
) -> List[Event]:
    """
     Filter events by key and values. This is useful for filtering events that have been added to a list of log events and are no longer in the log.
     
     @param events - List of events to filter. Must be sorted by time
     @param key - Key to filter by.
     @param vals - Values to filter by. If exclude is True events that don't match are returned.
     @param exclude - If True events that match are excluded from the returned list. Default is False. The filter will be applied in the order of events that were added to the list.
     
     @return A list of events that match the criteria specified by key and valebers. Note that the event list is modified
    """
    def predicate(event):
        """
         Checks if the key is in vals. This is used to filter events that have been sent to the API
         
         @param event - The event to be checked
         
         @return True if the key is in vals False if not or if the key is not in vals ( in which case it is ignored
        """
        return key in event.data and event.data[key] in vals

    # Returns a list of events that satisfy the predicate.
    if exclude:
        return [e for e in events if not predicate(e)]
    else:
        return [e for e in events if predicate(e)]


def filter_keyvals_regex(events: List[Event], key: str, regex: str) -> List[Event]:
    """
     Filter events by key values matching regular expression. This is useful for filtering events that have been created using : func : ` create_event `.
     
     @param events - List of events to filter. Must be sorted by key
     @param key - Key to filter by.
     @param regex - Regular expression to match key values against. Must be a string of regular expresions.
     
     @return A list of events that match the regex. The regex is compiled and matched against the key value. If the regex doesn't match any key value an empty list is returned
    """
    r = re.compile(regex)

    def predicate(event):
        """
         Predicate to determine if event matches regular expression. This is used by L { Event. filter } and L { Event. filter_regex }
         
         @param event - Event to be checked.
         
         @return True if match False otherwise. >>> event = Event ('hello') Traceback ( most recent call last ) : Exception :
        """
        return key in event.data and bool(r.findall(event.data[key]))

    return [e for e in events if predicate(e)]
