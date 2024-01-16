import iso8601
from typing import Optional, Callable, Dict, Any, List
from inspect import signature
from functools import wraps
from datetime import timedelta

from aw_core.models import Event
from aw_datastore import Datastore

from aw_transform import (
    filter_period_intersect,
    filter_keyvals,
    filter_keyvals_regex,
    period_union,
    union_no_overlap,
    categorize,
    tag,
    Rule,
    merge_events_by_keys,
    chunk_events_by_key,
    sort_by_timestamp,
    sort_by_duration,
    sum_durations,
    concat,
    split_url_events,
    simplify_string,
    flood,
    limit_events,
)

from .exceptions import QueryFunctionException


def _verify_bucket_exists(datastore, bucketname):
    """
     Verify that a bucket exists. This is a helper function for : func : ` _get_bucket ` to make sure we don't have an error in the middle of a query.
     
     @param datastore - The datastore to use for the query. Must be a subclass of
     @param bucketname - The name of the bucket to check for.
     
     @return None if the bucket exists otherwise an exception is raised with the message of the problem that was encountered in the query
    """
    # Returns the bucket with the given name.
    if bucketname in datastore.buckets():
        return
    else:
        raise QueryFunctionException(f"There's no bucket named '{bucketname}'")


def _verify_variable_is_type(variable, t):
    """
     Verifies that the passed variable is of the expected type. This is a helper function for _verify_variable_is_type_of_function_call
     
     @param variable - The variable to be verified
     @param t - The type to check against. It must be an instance of
    """
    # Raise QueryFunctionException if variable passed to function call is of invalid type.
    if not isinstance(variable, t):
        raise QueryFunctionException(
            "Variable '{}' passed to function call is of invalid type. Expected {} but was {}".format(
                variable, t, type(variable)
            )
        )


# TODO: proper type checking (typecheck-decorator in pypi?)


TNamespace = Dict[str, Any]
TQueryFunction = Callable[..., Any]


"""
    Declarations
"""
functions: Dict[str, TQueryFunction] = {}


def q2_function(transform_func=None):
    """
     Decorator for query functions. Automatically adds mock arguments for Datastore and TNamespace if they don't exist in function signature
     
     @param transform_func - function to use as transform
     
     @return decorated function that takes datastore and namespace as first argument and returns a tuple of datastore and namespace as
    """

    def h(f):
        """
         Decorator for functions that need to be wrapped. This is useful for transforming functions that do not need to be wrapped in a datastore and are expected to take a datastore and namespace argument
         
         @param f - function to be wrapped.
         
         @return wrapped function with correct arguments and namespace argument stripped from function name and docstring if it lacks it in
        """
        sig = signature(f)
        # If function lacks docstring, use docstring from underlying function in aw_transform
        # This function is used to generate documentation for the transform function.
        if transform_func and transform_func.__doc__ and not f.__doc__:
            f.__doc__ = ".. note:: Documentation automatically copied from underlying function `aw_transform.{func_name}`\n\n{func_doc}".format(
                func_name=transform_func.__name__, func_doc=transform_func.__doc__
            )

        @wraps(f)
        def g(datastore: Datastore, namespace: TNamespace, *args, **kwargs):
            """
             Wrapper for functions that don't need it. This is a convenience function to be used as a decorator in a function signature
             
             @param datastore - The datastore to use for the function
             @param namespace - The namespace to use for the function ( must be in the datastore's annotation )
             
             @return The result of the function's call to the function wrapped in a function with the datastore and namespace
            """
            # Remove datastore and namespace argument for functions that don't need it
            args = (datastore, namespace, *args)
            # If the signature is a namespace or a namespace it is not a namespace.
            if TNamespace not in (sig.parameters[p].annotation for p in sig.parameters):
                args = (args[0], *args[2:])
            # If Datastore is not in sig. parameters return None.
            if Datastore not in (sig.parameters[p].annotation for p in sig.parameters):
                args = args[1:]
            return f(*args, **kwargs)

        fname = f.__name__
        # fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname q2_ fname
        if fname[:3] == "q2_":
            fname = fname[3:]
        functions[fname] = g
        return g

    return h


def q2_typecheck(f):
    """
     Decorator that typechecks a function. Note that this decorator is intended to be used as a decorator in conjunction with : func : ` q2_decorator `.
     
     @param f - function to be typechecked. The function must have a signature that matches the signature of the function passed to it.
     
     @return a function that wraps the function with type checking applied to the arguments of the function as well as checking the type of the return values
    """
    """Decorator that typechecks using `_verify_variable_is_type`"""
    sig = signature(f)

    @wraps(f)
    def g(*args, **kwargs):
        """
         Check that parameters are correct and pass to function. This is a hack to make it easier to read the documentation of : func : ` ~functools. functools. g `.
         
         
         @return result of f ( * args ** kwargs ) or None if there is no result to return ( in which case we don't return
        """
        # FIXME: If the first argument passed to a query2 function is a straight [] then the second argument disappears from the argument list for unknown reasons, which breaks things
        # Check that all parameters are of the correct type.
        for i, p in enumerate(sig.parameters):
            param = sig.parameters[p]

            # print(f"Checking that param ({param}) was {param.annotation}, value: {args[i]}")
            # FIXME: Won't check keyword arguments
            # Check if the annotation is a list str int float or list string int float
            if (
                param.annotation in [list, str, int, float]
                and param.default == param.empty
            ):
                _verify_variable_is_type(args[i], param.annotation)

        return f(*args, **kwargs)

    return g


"""
    Getting buckets
"""


@q2_function()
@q2_typecheck
def q2_find_bucket(
    datastore: Datastore, filter_str: str, hostname: Optional[str] = None
):
    """
     Find bucket by filter_str ( to avoid hardcoding bucket names ). If hostname is specified it will be used to match the hostname of the bucket
     
     @param datastore - Datastore to search in.
     @param filter_str - Bucket name to search for. This is a string like'my - bucket '
     @param hostname - Optional hostname to match.
     
     @return A : class :
    """
    # Returns the bucket that matches the hostname.
    for bucket in datastore.buckets():
        # Returns the bucket if the filter string is in the bucket metadata.
        if filter_str in bucket:
            bucket_metadata = datastore[bucket].metadata()
            # Returns the bucket if hostname is given.
            if hostname:
                # Return the bucket that is the hostname of the bucket.
                if bucket_metadata["hostname"] == hostname:
                    return bucket
            else:
                return bucket
    raise QueryFunctionException(
        "Unable to find bucket matching '{}' (hostname filter set to '{}')".format(
            filter_str, hostname
        )
    )


"""
    Data gathering functions
"""


@q2_function()
@q2_typecheck
def q2_query_bucket(
    datastore: Datastore, namespace: TNamespace, bucketname: str
) -> List[Event]:
    """
     Query a bucket and return events. This is a wrapper around datastore. get that handles time parsing.
     
     @param datastore - Datastore to use for querying. Must be initialized with datastore_init
     @param namespace - Namespace to use for the query. Must contain STARTTIME and ENDTIME
     @param bucketname - Name of the bucket to query. Must be initialized with datastore_init
     
     @return List of events in the bucket. Raises QueryFunctionException if there is a problem with the data returned
    """
    _verify_bucket_exists(datastore, bucketname)
    try:
        starttime = iso8601.parse_date(namespace["STARTTIME"])
        endtime = iso8601.parse_date(namespace["ENDTIME"])
    except iso8601.ParseError:
        raise QueryFunctionException(
            "Unable to parse starttime/endtime for query_bucket"
        )
    return datastore[bucketname].get(starttime=starttime, endtime=endtime)


@q2_function()
@q2_typecheck
def q2_query_bucket_eventcount(
    datastore: Datastore, namespace: TNamespace, bucketname: str
) -> int:
    """
     Query event count for a bucket. This is a low - level function to be used by q2_query_bucket and q2_query_bucket_and_event.
     
     @param datastore - Datastore to access the data. Must be initialized with datastore_init.
     @param namespace - Namespace for the query. Must contain STARTTIME and ENDTIME
     @param bucketname - Name of the bucket to query.
     
     @return The number of events
    """
    _verify_bucket_exists(datastore, bucketname)
    starttime = iso8601.parse_date(namespace["STARTTIME"])
    endtime = iso8601.parse_date(namespace["ENDTIME"])
    return datastore[bucketname].get_eventcount(starttime=starttime, endtime=endtime)


"""
    Filtering functions
"""


@q2_function(filter_keyvals)
@q2_typecheck
def q2_filter_keyvals(events: list, key: str, vals: list) -> List[Event]:
    """
     Filter events by key and values. This is a wrapper around filter_keyvals with False as filter_keyvals
     
     @param events - List of events to filter
     @param key - Key to filter by ( case sensitive ).
     @param vals - Values to filter by ( case sensitive ).
     
     @return List of events that match the criteria. If no match is found an empty list is returned. Note that the order of events is preserved
    """
    return filter_keyvals(events, key, vals, False)


@q2_function(filter_keyvals)
@q2_typecheck
def q2_exclude_keyvals(events: list, key: str, vals: list) -> List[Event]:
    """
     Exclude events that match key and value. This is a wrapper around filter_keyvals that filters events based on the value of the key.
     
     @param events - List of events to filter. Must be sorted by key.
     @param key - Key to match. Must be a string.
     @param vals - Values to match. Must be a list.
     
     @return A list of events that don't match the key and value ( s ). The list is in the same order as events
    """
    return filter_keyvals(events, key, vals, True)


@q2_function(filter_keyvals_regex)
@q2_typecheck
def q2_filter_keyvals_regex(events: list, key: str, regex: str) -> List[Event]:
    """
     Filter events by key and regex. This is a wrapper around filter_keyvals_regex with support for Q2
     
     @param events - List of events to filter
     @param key - Key to filter by ( string ). E. g.
     @param regex - Regular expression to filter by ( string ).
     
     @return List of events that match the regex ( list of strings ). Example :. from iota import q2_client as client from iota_client. lib. event import Event q2_client. filter_keyvals_regex ( events'user. id'' admin '
    """
    return filter_keyvals_regex(events, key, regex)


@q2_function(filter_period_intersect)
@q2_typecheck
def q2_filter_period_intersect(events: list, filterevents: list) -> List[Event]:
    """
     Filter events that overlap period. This is equivalent to filter_period_intersect but with more flexibility to avoid having to re - evaluate the algorithm in a single pass.
     
     @param events - List of events to filter. Must be sorted by time.
     @param filterevents - List of events to filter. Must be sorted by time.
     
     @return List of events that overlap period. Note that events are returned in order of time and not in the same order
    """
    return filter_period_intersect(events, filterevents)


@q2_function(period_union)
@q2_typecheck
def q2_period_union(events1: list, events2: list) -> List[Event]:
    """
     Union of two quarters of events. This is equivalent to period_union ( events1 events2 )
     
     @param events1 - List of events to union
     @param events2 - List of events to union ( same length as events1 )
     
     @return List of events that are in both events1 and events2 or empty list if there is no such
    """
    return period_union(events1, events2)


@q2_function(limit_events)
@q2_typecheck
def q2_limit_events(events: list, count: int) -> List[Event]:
    """
     Limit a list of events to a certain number of events. This is a wrapper around limit_events to ensure that events are returned in the correct order.
     
     @param events - A list of events to limit. It is assumed that the user has already checked that they are not in the wrong order.
     @param count - The number of events to limit to. If this is less than the number of events in the list an empty list is returned.
     
     @return A list of events that fit the criteria given by the user. If there are less than count events the list is returned
    """
    return limit_events(events, count)


"""
    Merge functions
"""


@q2_function(merge_events_by_keys)
@q2_typecheck
def q2_merge_events_by_keys(events: list, keys: list) -> List[Event]:
    """
     Merge events by keys. This is a wrapper around merge_events_by_keys that does not take into account keys that are in the middle of a merge.
     
     @param events - List of events to merge. Must be sorted by key.
     @param keys - List of keys to merge. Must be sorted by key.
     
     @return List of events merged by keys. The order of events is undefined but may be different depending on the implementation
    """
    return merge_events_by_keys(events, keys)


@q2_function(chunk_events_by_key)
@q2_typecheck
def q2_chunk_events_by_key(events: list, key: str) -> List[Event]:
    """
     Chunk events by key. This is a wrapper around chunk_events_by_key to avoid having to iterate over events in a single query.
     
     @param events - List of events to chunk. Must be sorted by key.
     @param key - Key to use for chunking. If key is None all events will be returned.
     
     @return List of events chunked by key. Empty list if no events are found in the list. Raises ValueError if there is a problem
    """
    return chunk_events_by_key(events, key)


"""
    Sort functions
"""


@q2_function(sort_by_timestamp)
@q2_typecheck
def q2_sort_by_timestamp(events: list) -> List[Event]:
    """
     Sort events by timestamp. This is a wrapper around sort_by_timestamp that does not check for duplicate timestamps.
     
     @param events - List of events to sort. Must be sorted in ascending order.
     
     @return A list of sorted events. The events are returned in the same order as they were passed in but with duplicates
    """
    return sort_by_timestamp(events)


@q2_function(sort_by_duration)
@q2_typecheck
def q2_sort_by_duration(events: list) -> List[Event]:
    """
     Sort events by duration. This is a wrapper around sort_by_duration that does not check for validity of the input
     
     @param events - List of events to sort
     
     @return List of sorted events in order of time ( ascending ) or empty list if there are no events in
    """
    return sort_by_duration(events)


"""
    Summarizing functions
"""


@q2_function(sum_durations)
@q2_typecheck
def q2_sum_durations(events: list) -> timedelta:
    """
     Sum the durations of a list of events. This is equivalent to : func : ` sum_durations ` but with more flexibility to avoid overflowing the result.
     
     @param events - A list of events. Each event is a : class : ` ~datetime. timedelta ` object.
     
     @return The sum of the durations of the events in ` ` events ` `. >>> events = [ 1 2 3 ] >>> sum_durations ( events )
    """
    return sum_durations(events)


@q2_function(concat)
@q2_typecheck
def q2_concat(events1: list, events2: list) -> List[Event]:
    """
     Concatenate two lists of events. This is equivalent to : func : ` concat ` but the events are assumed to be sorted by time.
     
     @param events1 - A list of events to concatenate. It is assumed that the first list is sorted in ascending order.
     @param events2 - A list of events to concatenate. It is assumed that the second list is sorted in ascending order.
     
     @return A list of events that are the result of concatenating the two lists of events. If there is an error the list is empty
    """
    return concat(events1, events2)


@q2_function(union_no_overlap)
@q2_typecheck
def q2_union_no_overlap(events1: list, events2: list) -> List[Event]:
    """
     Union of two sets of events without overlapping. This is equivalent to : func : ` union_no_overlap `
     
     @param events1 - A list of events to union. The length of this list must be at least 2.
     @param events2 - A list of events to union. The length of this list must be at least 2.
     
     @return A list of events that are the union of the two sets of events. Each event is a tuple of two elements
    """
    return union_no_overlap(events1, events2)


"""
    Flood functions
"""


@q2_function(flood)
@q2_typecheck
def q2_flood(events: list) -> List[Event]:
    """
     Flood a list of events to a maximum of Q2. This is a wrapper around : func : ` flood `
     
     @param events - A list of events to flood
     
     @return A list of events that are the maximum of Q2 ( max 50 ). Example :. >>> events = [ event1 event2 event
    """
    return flood(events)


"""
    Watcher specific functions
"""


@q2_function(split_url_events)
@q2_typecheck
def q2_split_url_events(events: list) -> List[Event]:
    """
     Splits events into URL events. This is a wrapper around split_url_events. The purpose of this wrapper is to avoid having to re - create the events in a way that is consistent with Q2's event handling code.
     
     @param events - A list of events to split. Each event is a list of ` Event ` objects.
     
     @return A list of ` Event ` objects that correspond to the events in the list. The list may be empty
    """
    return split_url_events(events)


@q2_function(simplify_string)
@q2_typecheck
def q2_simplify_window_titles(events: list, key: str) -> List[Event]:
    """
     Simplify window titles by removing spaces and other non - ASCII characters. This is useful for example when you want to show a title that is more than 20 characters long and the title is too long.
     
     @param events - List of : class : ` q2. Event ` objects
     @param key - Key to use for simplifying.
     
     @return List of : class : ` q2. Event ` objects that have been simplified to a list of
    """
    return simplify_string(events, key=key)


"""
    Test functions
"""


@q2_function()
@q2_typecheck
def q2_nop():
    """
     No operation function for unittesting. It is used to test the Q2_nop function of the Quantum Programming Language ( Q2 ).
     
     
     @return 1 for success 0 for failure >>> from sympy. solvers. myprefix import q
    """
    """No operation function for unittesting"""
    return 1


"""
    Classify
"""


@q2_function(categorize)
@q2_typecheck
def q2_categorize(events: list, classes: list):
    """
     Categorize events according to classes. This is a wrapper around : func : ` categorize ` that creates a list of tuples ( class rule_dict ) for each class and passes them to
     
     @param events - A list of events to categorize
     @param classes - A list of tuples ( class rule_dict )
     
     @return A list of events categorized according to the given classes in the order they were passed in and the classes
    """
    classes = [(_cls, Rule(rule_dict)) for _cls, rule_dict in classes]
    return categorize(events, classes)


@q2_function(tag)
@q2_typecheck
def q2_tag(events: list, classes: list):
    """
     Tag a list of events with a list of Q2 classes. This is a convenience function for tag ()
     
     @param events - A list of events to tag
     @param classes - A list of Q2 classes to tag the events with
     
     @return A list of tag ( s ) that can be used to add tags to the events as they are
    """
    classes = [(_cls, Rule(rule_dict)) for _cls, rule_dict in classes]
    return tag(events, classes)
