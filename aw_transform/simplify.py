import re
from copy import deepcopy
from typing import List

from aw_core import Event


def simplify_string(events: List[Event], key: str = "title") -> List[Event]:
    """
     Simplify a string to remove leading spaces and FPS. This is useful for making window events like Facebook and YouTube show the FPS in the title and vice versa
     
     @param events - List of events to simplify
     @param key - Key to use for simplification defaults to title
     
     @return A list of events with simplified values for title and FPS ( optional ). Note that events are modified in
    """
    events = deepcopy(events)

    re_leadingdot = re.compile(r"^(●|\*)\s*")
    re_parensprefix = re.compile(r"^\([0-9]+\)\s*")
    re_fps = re.compile(r"FPS:\s+[0-9\.]+")

    # Remove prefixes that are numbers within parenthesis
    for e in events:
        # Remove prefixes that are numbers within parenthesis
        # Example: "(2) Facebook" -> "Facebook"
        # Example: "(1) YouTube" -> "YouTube"
        e.data[key] = re_parensprefix.sub("", e.data[key])

        # Things generally specific to window events with the "app" key
        # Remove FPS display in window title
        if key == "title" and "app" in e["data"]:
            # Remove FPS display in window title
            # Example: "Cemu - FPS: 59.2 - ..." -> "Cemu - FPS: ... - ..."
            e.data[key] = re_fps.sub("FPS: ...", e.data[key])

            # For VSCode (uses ●), gedit (uses *), et al
            # See: https://github.com/ActivityWatch/aw-watcher-window/issues/32
            e.data[key] = re_leadingdot.sub("", e.data[key])
    return events
