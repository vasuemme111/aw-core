import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import List, Optional

from . import dirs
from .decorators import deprecated

# NOTE: Will be removed in a future version since it's not compatible
#       with running a multi-service process.
# TODO: prefix with `_`
log_file_path = None


@deprecated
def get_log_file_path() -> Optional[str]:  # pragma: no cover
    """
     Get the path to the log file. This is deprecated : use get_latest_log_file instead.
     
     
     @return The path to the log file or None if not found or an error occurred during reading the log file
    """
    """DEPRECATED: Use get_latest_log_file instead."""
    return log_file_path


def setup_logging(
    name: str,
    testing=False,
    verbose=False,
    log_stderr=True,
    log_file=False,
):  # pragma: no cover
    """
     Setup logging for AW components. This is a wrapper around : func : ` logging. getLogger ` to allow us to set up a logging handler for each AW component.
     
     @param name - The name of the logger. Used for logging messages to the console
     @param testing - Whether or not we are testing
     @param verbose - Whether or not to log to stderr ( debug )
     @param log_stderr - Whether or not to log to stderr
     @param log_file - Whether or not to log to file (
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    root_logger.handlers = []

    # run with LOG_LEVEL=DEBUG to customize log level across all AW components
    log_level = os.environ.get("LOG_LEVEL")
    # Set the logging level to the current logging level.
    if log_level:
        # Set the logging level as specified in env var
        if hasattr(logging, log_level.upper()):
            root_logger.setLevel(getattr(logging, log_level.upper()))
        else:
            root_logger.warning(
                f"No logging level called {log_level} (as specified in env var)"
            )

    # Add a handler for stderr output.
    if log_stderr:
        root_logger.addHandler(_create_stderr_handler())
    # Add a handler for the file handler.
    if log_file:
        root_logger.addHandler(_create_file_handler(name, testing=testing))

    def excepthook(type_, value, traceback):
        """
         Catch exceptions and log them to root_logger. This is a wrapper around sys. excepthook which logs the exception if log_stderr is set to False.
         
         @param type_ - The type of exception raised. Should be one of : exc : ` sys. exc_info `
         @param value - The value of the exception
         @param traceback
        """
        root_logger.exception("Unhandled exception", exc_info=(type_, value, traceback))
        # call the default excepthook if log_stderr isn't true
        # (otherwise it'll just get duplicated)
        # If log_stderr is set to true then sys. excepthook__ type_ value traceback is logged and the traceback is not logged.
        if not log_stderr:
            sys.__excepthook__(type_, value, traceback)

    sys.excepthook = excepthook


def _get_latest_log_files(name, testing=False) -> List[str]:  # pragma: no cover
    """
     Get a list of log files for a given test. This is a helper to : func : ` get_log_files `.
     
     @param name - The name of the test. This must be a fully qualified path e. g.
     @param testing - Whether or not to include the testing log file.
     
     @return A list of log file paths sorted by latest. The order is : 1. name 2. test
    """
    """
    Returns a list with the paths of all available logfiles for `name`,
    sorted by latest first.
    """
    log_dir = dirs.get_log_dir(name)
    files = filter(lambda filename: name in filename, os.listdir(log_dir))
    files = filter(
        lambda filename: "testing" in filename
        if testing
        else "testing" not in filename,
        files,
    )
    return [os.path.join(log_dir, filename) for filename in sorted(files, reverse=True)]


def get_latest_log_file(name, testing=False) -> Optional[str]:  # pragma: no cover
    """
     Get the filename of the latest log file with the given name. This is useful when you want to read the logfile of another activity watch service.
     
     @param name - The name of the activity watch file that will be used as the base for the filename
     @param testing - If True will use the test log instead of the
    """
    """
    Returns the filename of the last logfile with ``name``.
    Useful when you want to read the logfile of another ActivityWatch service.
    """
    last_logs = _get_latest_log_files(name, testing=testing)
    return last_logs[0] if last_logs else None


def _create_stderr_handler() -> logging.Handler:  # pragma: no cover
    """
     Create a handler that writes to stderr. This is useful for debugging and to ensure that stderr is printed to the console in a human readable format.
     
     
     @return A logging. Handler to use for outputting to stderr ( or logging. StreamHandler ). Note that the handler does not have a formatter
    """
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(_create_human_formatter())

    return stderr_handler


def _create_file_handler(
    name, testing=False, log_json=False
) -> logging.Handler:  
    """
     Creates a handler that logs to a file. If testing is True the file will be named " test_ " otherwise it will be named ". log "
     
     @param name - The name of the log
     @param testing - Whether or not we are testing
     @param log_json - Whether or not to use json logs
     
     @return An instance of logging. Handler to be used for logging to a file. This is a function that takes a name and returns a log
    """
    # pragma: no cover
    log_dir = dirs.get_log_dir(name)

    # Set logfile path and name
    global log_file_path

    # Should result in something like:
    # $LOG_DIR/aw-server_testing_2017-01-05T00:21:39.log
    file_ext = ".log.json" if log_json else ".log"
    now_str = str(datetime.now().replace(microsecond=0).isoformat()).replace(":", "-")
    log_name = name + "_" + ("testing_" if testing else "") + now_str + file_ext
    log_file_path = os.path.join(log_dir, log_name)

    # Create rotating logfile handler, max 10MB per file, 3 files max
    # Prevents logfile from growing too large, like in:
    #  - https://github.com/ActivityWatch/activitywatch/issues/815#issue-1423555466
    #  - https://github.com/ActivityWatch/activitywatch/issues/756#issuecomment-1266662861
    fh = RotatingFileHandler(
        log_file_path, mode="a", maxBytes=10 * 1024 * 1024, backupCount=3
    )
    fh.setFormatter(_create_human_formatter())

    return fh


def _create_human_formatter() -> logging.Formatter:  # pragma: no cover
    """
     Create a formatter that prints to the console. This is useful for debugging the log messages that don't fit into the console.
     
     
     @return A : class : ` logging. Formatter ` with the same format as the one returned by : func : ` asctime `
    """
    return logging.Formatter(
        "%(asctime)s [%(levelname)-5s]: %(message)s  (%(name)s:%(lineno)s)",
        "%Y-%m-%d %H:%M:%S",
    )
