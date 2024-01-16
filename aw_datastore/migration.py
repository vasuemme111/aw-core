import logging
import os
from typing import List, Optional

from aw_core.dirs import get_data_dir

from .storages import AbstractStorage

logger = logging.getLogger(__name__)


def detect_db_files(
    data_dir: str, datastore_name: Optional[str] = None, version=None
) -> List[str]:
    """
     Detect database files in data_dir. This is a helper function to get a list of files that match the datastore_name and / or version
     
     @param data_dir - directory in which to look for databases
     @param datastore_name - name of the datastore to look for
     @param version - version of the datastore to look for ( None for all )
     
     @return list of database files or empty list if none are found ( not an error or no files found at all
    """
    db_files = [filename for filename in os.listdir(data_dir)]
    # Return the datastore_name of the datastore.
    if datastore_name:
        db_files = [
            filename
            for filename in db_files
            if filename.split(".")[0] == datastore_name
        ]
    # Return the version of the database.
    if version:
        db_files = [
            filename for filename in db_files if filename.split(".")[1] == f"v{version}"
        ]
    return db_files


def check_for_migration(datastore: AbstractStorage):
    """
     Check if there is a peewee v2 database and migrate if necessary. This is called by : py : func : ` check_for_migration ` and should be used as a context manager.
     
     @param datastore - datastore to migrate from peewee v1
    """
    data_dir = get_data_dir("aw-server")

    # Migrate from peewee v2 to sqlite
    if datastore.sid == "sqlite":
        peewee_type = "peewee-sqlite"
        peewee_name = peewee_type + ("-testing" if datastore.testing else "")
        # Migrate from peewee v2
        peewee_db_v2 = detect_db_files(data_dir, peewee_name, 2)
        # If peewee_db_v2 is not empty then we need to convert the peewee_db_v2 to sqlite_v1.
        if len(peewee_db_v2) > 0:
            peewee_v2_to_sqlite_v1(datastore)


def peewee_v2_to_sqlite_v1(datastore):
    """
     Migrate peewee v2 to sqlite v1 This is a migration function that migrates the data stored in the peewee database from version 2 to version 1
     
     @param datastore - The datastore to use for
    """
    logger.info("Migrating database from peewee v2 to sqlite v1")
    from .storages import PeeweeStorage

    pw_db = PeeweeStorage(datastore.testing)
    # Fetch buckets and events
    buckets = pw_db.buckets()
    # Insert buckets and events to new db
    # Migrates all buckets to the database.
    for bucket_id in buckets:
        logger.info(f"Migrating bucket {bucket_id}")
        bucket = buckets[bucket_id]
        datastore.create_bucket(
            bucket["id"],
            bucket["type"],
            bucket["client"],
            bucket["hostname"],
            bucket["created"],
            bucket["name"],
        )
        bucket_events = pw_db.get_events(bucket_id, -1)
        datastore.insert_many(bucket_id, bucket_events)
    logger.info("Migration of peewee v2 to sqlite v1 finished")
