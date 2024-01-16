from typing import Pattern, List, Iterable, Tuple, Dict, Optional, Any
from functools import reduce
import re

from aw_core import Event


Tag = str
Category = List[str]


class Rule:
    regex: Optional[Pattern]
    select_keys: Optional[List[str]]
    ignore_case: bool

    def __init__(self, rules: Dict[str, Any]) -> None:
        """
         Initializes the class with the rules. This is the entry point for the class. It should be called from the __init__ method of the class
         
         @param rules - A dictionary that contains the rules
         
         @return None if there is no rules otherwise a boolean indicating whether or not to select keys and / or case
        """
        self.select_keys = rules.get("select_keys", None)
        self.ignore_case = rules.get("ignore_case", False)

        # NOTE: Also checks that the regex isn't an empty string (which would erroneously match everything)
        regex_str = rules.get("regex", None)
        self.regex = (
            re.compile(
                regex_str, (re.IGNORECASE if self.ignore_case else 0) | re.UNICODE
            )
            if regex_str
            else None
        )

    def match(self, e: Event) -> bool:
        """
         Match an event against this filter. This is used to determine if the event should be processed by the filter
         
         @param e - The event to be checked
         
         @return True if the event matches the filter False if it doesn't or if there is no match ( no keys
        """
        # Returns a list of values for the selected keys.
        if self.select_keys:
            values = [e.data.get(key, None) for key in self.select_keys]
        else:
            values = list(e.data.values())
        # Return True if any of the values in the values list match the regex.
        if self.regex:
            # Return True if any of the values in values match the regex.
            for val in values:
                # Return True if val is a string or a regex.
                if isinstance(val, str) and self.regex.search(val):
                    return True
        return False


def categorize(
    events: List[Event], classes: List[Tuple[Category, Rule]]
) -> List[Event]:
    """
     Categorize a list of events. This is a wrapper around _categorize_one that applies the classes to each event
     
     @param events - The events to categorize.
     @param classes - The classes to apply to each event. This should be a list of tuples where the first element is the category and the second element is the rule that
    """
    return [_categorize_one(e, classes) for e in events]


def _categorize_one(e: Event, classes: List[Tuple[Category, Rule]]) -> Event:
    """
     Categorize one event according to the rules. This is a helper function for : func : ` _fix_events `
     
     @param e - The event to categorize.
     @param classes - A list of tuples where each tuple is a rule and the first element is a category.
     
     @return The event with the category added to it if it matches one of the rules. Otherwise it is returned
    """
    e.data["$category"] = _pick_category(
        [_cls for _cls, rule in classes if rule.match(e)]
    )
    return e


def tag(events: List[Event], classes: List[Tuple[Tag, Rule]]) -> List[Event]:
    """
     Tag events with a list of classes. This is a wrapper around _tag_one for use in tests
     
     @param events - List of events to tag
     @param classes - List of classes to tag with e. g.
     
     @return List of events with tags replaced with rules or empty list if no tags were found ( in which case it is a list
    """
    return [_tag_one(e, classes) for e in events]


def _tag_one(e: Event, classes: List[Tuple[Tag, Rule]]) -> Event:
    """
     Tag a single event. This is a helper for : meth : ` _tag ` and : meth : ` _tag_and_rule `
     
     @param e - The event to tag.
     @param classes - A list of tag and rule pairs. Each pair is a tuple of the form ` ` ( tag rule ) ` `
     
     @return The event with tags
    """
    e.data["$tags"] = [_cls for _cls, rule in classes if rule.match(e)]
    return e


def _pick_category(tags: Iterable[Category]) -> Category:
    """
     Pick the most appropriate category from a list of tags. This is used to determine which category to use when creating a category - tree
     
     @param tags - list of tags to pick the category from
     
     @return the category that should be used for the tree - rooted tag - tree or " Uncategorized
    """
    return reduce(_pick_deepest_cat, tags, ["Uncategorized"])


def _pick_deepest_cat(t1: Category, t2: Category) -> Category:
    """
     Pick deepest category from t1 and t2. This is used to determine the most common category for a reduction
     
     @param t1 - The accumulator of the reduction
     @param t2 - The target of the reduction ( must be sorted )
     
     @return The deepest category among t1 and t2 or the accumulator if there are no common categories in
    """
    # t1 will be the accumulator when used in reduce
    # Always bias against t1, since it could be "Uncategorized"
    return t2 if len(t2) >= len(t1) else t1
