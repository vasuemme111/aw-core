import os
import json


def _this_dir() -> str:
    """
     Return the directory where this file resides. This is useful for debugging the file system in a way that doesn't have to be rebuilt every time it's needed.
     
     
     @return The directory where this file resides or None if it doesn't exist in the current directory ( or is missing
    """
    return os.path.dirname(os.path.abspath(__file__))


def _schema_dir() -> str:
    """
     Path to schema directory. This is used to determine the location of the schemas directory. It does not need to be a directory but is relative to the directory that is created by _create_schema_dir ().
     
     
     @return path to schema directory ( relative to the directory that is created by _create_schema_dir ()
    """
    return os.path.join(os.path.dirname(_this_dir()), "aw_core", "schemas")


def get_json_schema(name: str) -> dict:
    """
     Load a JSON schema from disk. This is a wrapper around json. load () to allow us to load the schema without having to re - import it every time
     
     @param name - Name of the schema to load
     
     @return Dictionary of the schema or None if not found or an error occurred ( for example if there was a problem loading
    """
    with open(os.path.join(_schema_dir(), name + ".json")) as f:
        data = json.load(f)
    return data


# Print the JSON schema for the event.
if __name__ == "__main__":
    print(get_json_schema("event"))
