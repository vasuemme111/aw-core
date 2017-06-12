import logging
import random
from datetime import datetime, timedelta, timezone

import pytest

from . import context

from aw_core.models import Event
from aw_datastore import get_storage_methods

from .utils import param_datastore_objects, param_testing_buckets_cm


logging.basicConfig(level=logging.DEBUG)

# Useful when you just want some placeholder time in your events, saves typing
now = datetime.now(timezone.utc)


def test_get_storage_methods():
    assert get_storage_methods()


@pytest.mark.parametrize("datastore", param_datastore_objects())
def test_get_buckets(datastore):
    """
    Tests fetching buckets
    """
    datastore.buckets()


@pytest.mark.parametrize("datastore", param_datastore_objects())
def test_create_bucket(datastore):
    name = "A label/name for a test bucket"
    bid = "test-identifier"
    bucket = datastore.create_bucket(bucket_id=bid, type="test", client="test", hostname="test", name=name)
    try:
        assert bid == bucket.metadata()["id"]
        assert "test" == bucket.metadata()["type"]
        assert "test" == bucket.metadata()["client"]
        assert "test" == bucket.metadata()["hostname"]
        assert name == bucket.metadata()["name"]
    finally:
        datastore.delete_bucket(bid)
    assert bid not in datastore.buckets()


@pytest.mark.parametrize("datastore", param_datastore_objects())
def test_nonexistant_bucket(datastore):
    """
    Tests that a KeyError is raised if you request a non-existant bucket
    """
    with pytest.raises(KeyError):
        datastore["I-do-not-exist"]


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_insert_one(bucket_cm):
    """
    Tests inserting one event into a bucket
    """
    with bucket_cm as bucket:
        l = len(bucket.get())
        event = Event(label="test", timestamp=now, duration=timedelta(seconds=1), data={"key": "val"})
        bucket.insert(event)
        fetched_events = bucket.get()
        assert l + 1 == len(fetched_events)
        assert Event == type(fetched_events[0])
        assert event == fetched_events[0]
        logging.info(event)
        logging.info(fetched_events[0].to_json_str())


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_empty_bucket(bucket_cm):
    """
    Ensures empty buckets are empty
    """
    with bucket_cm as bucket:
        assert 0 == len(bucket.get())


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_insert_many(bucket_cm):
    """
    Tests that you can insert many events at the same time to a bucket
    """
    num_events = 5000
    with bucket_cm as bucket:
        events = (num_events * [Event(label="test", timestamp=now, duration=timedelta(seconds=1), data={"key": "val"})])
        bucket.insert(events)
        fetched_events = bucket.get(limit=-1)
        assert num_events == len(fetched_events)
        for e, fe in zip(events, fetched_events):
            assert e == fe


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_insert_badtype(bucket_cm):
    """
    Tests that you cannot insert non-event types into a bucket
    """
    with bucket_cm as bucket:
        l = len(bucket.get())
        badevent = 1
        with pytest.raises(TypeError):
            bucket.insert(badevent)
        assert l == len(bucket.get())


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_get_ordered(bucket_cm):
    """
    Makes sure that received events are ordered
    """
    with bucket_cm as bucket:
        eventcount = 10
        events = []
        for i in range(10):
            events.append(Event(label="test",
                                timestamp=now + timedelta(seconds=i)))
        random.shuffle(events)
        print(events)
        bucket.insert(events)
        fetched_events = bucket.get(-1)
        for i in range(eventcount - 1):
            print("1:" + fetched_events[i].to_json_str())
            print("2:" + fetched_events[i + 1].to_json_str())
            assert fetched_events[i].timestamp > fetched_events[i + 1].timestamp


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_get_datefilter(bucket_cm):
    """
    Tests the datetimefilter when fetching events
    """
    with bucket_cm as bucket:
        eventcount = 10
        events = []
        for i in range(10):
            events.append(Event(label="test",
                                timestamp=now + timedelta(seconds=i)))
        bucket.insert(events)

        # Starttime
        for i in range(eventcount):
            fetched_events = bucket.get(-1, starttime=events[i].timestamp)
            assert eventcount - i - 1 == len(fetched_events)

        # Endtime
        for i in range(eventcount):
            fetched_events = bucket.get(-1, endtime=events[i].timestamp)
            assert i == len(fetched_events)

        # Both
        for i in range(eventcount):
            for j in range(i + 1, eventcount):
                fetched_events = bucket.get(starttime=events[i].timestamp, endtime=events[j].timestamp)
                assert j - i - 1 == len(fetched_events)


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_insert_invalid(bucket_cm):
    with bucket_cm as bucket:
        event = "not a real event"
        with pytest.raises(TypeError):
            bucket.insert(event)


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_get_last(bucket_cm):
    """
    Tests setting the result limit when fetching events
    """
    now = datetime.now()
    second = timedelta(seconds=1)
    with bucket_cm as bucket:
        events = [Event(data={"label": "test"}, timestamp=ts, duration=timedelta(0)) for ts in [now + second, now + second * 2, now + second * 3]]

        for event in events:
            bucket.insert(event)

        assert bucket.get(limit=1)[0] == events[-1]
        for event in bucket.get(limit=5):
            print(event.timestamp, event.data["label"])


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_limit(bucket_cm):
    """
    Tests setting the result limit when fetching events
    """
    with bucket_cm as bucket:
        for i in range(5):
            bucket.insert(Event(label="test", timestamp=now))

        print(len(bucket.get(limit=1)))
        assert 0 == len(bucket.get(limit=0))
        assert 1 == len(bucket.get(limit=1))
        assert 3 == len(bucket.get(limit=3))
        assert 5 == len(bucket.get(limit=5))
        assert 5 == len(bucket.get(limit=-1))


@pytest.mark.parametrize("bucket_cm", param_testing_buckets_cm())
def test_get_metadata(bucket_cm):
    """
    Tests the get_metadata function
    """
    with bucket_cm as bucket:
        print(bucket.ds.storage_strategy)
        metadata = bucket.metadata()
        print(metadata)
        assert 'created' in metadata
        assert 'client' in metadata
        assert 'hostname' in metadata
        assert 'id' in metadata
        assert 'name' in metadata
        assert 'type' in metadata
