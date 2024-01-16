"""
The idea behind this `aw` or `aw-cli` wrapper script is to act as a collection of helper tools,
and perhaps even as a way to list and run ActivityWatch modules on a system (a bit like aw-qt, but without the GUI).
"""

from pathlib import Path
from datetime import datetime
import subprocess

import click

from aw_cli.log import find_oldest_log, print_log, LOGLEVELS
from typing import Optional


@click.group()
@click.option("--testing", is_flag=True)
def main(testing: bool = False):
    """
     This is the entry point for the script. It does nothing except return the code to the caller.
     
     @param testing - If True run the script in testing mode
    """
    pass


@main.command()
@click.pass_context
def qt(ctx):
    """
     Run qt. This is a wrapper around aw - qt. If you want to run tests you must call this function in test_case.
     
     @param ctx - Context object passed by : func : ` waflib. Context. from_command_line `
     
     @return The exit code of
    """
    return subprocess.call(
        ["aw-qt"] + (["--testing"] if ctx.parent.params["testing"] else [])
    )


@main.command()
def directories():
    """
     Print all directories used to store data and log files in / var / lib / aw_core.
    """
    # Print all directories
    from aw_core.dirs import get_data_dir, get_config_dir, get_cache_dir, get_log_dir

    print("Directory paths used")
    print(" - config: ", get_config_dir(None))
    print(" - data:   ", get_data_dir(None))
    print(" - logs:   ", get_log_dir(None))
    print(" - cache:  ", get_cache_dir(None))


@main.command()
@click.pass_context
@click.argument("module_name", type=str, required=False)
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Only show logs since this date",
)
@click.option(
    "--level",
    type=click.Choice(LOGLEVELS),
    help="Only show logs of this level, or higher.",
)
def logs(
    ctx,
    module_name: Optional[str] = None,
    since: Optional[datetime] = None,
    level: Optional[str] = None,
):
    """
     Print the oldest log. If no module_name is specified all logs are printed. This is useful for debugging purposes.
     
     @param ctx - context object ( Required ). Required. The context object
     @param module_name - name of the module to print logs for
     @param since - date and time to print
     @param level - log level to print ( optional default : INFO
    """
    from aw_core.dirs import get_log_dir

    testing = ctx.parent.params["testing"]
    logdir: Path = Path(get_log_dir(None))

    # find the oldest logfile in each of the subdirectories in the logging directory, and print the last lines in each one.

    # Prints the oldest log file.
    if module_name:
        print_oldest_log(logdir / module_name, testing, since, level)
    else:
        # Prints the oldest log file.
        for subdir in sorted(logdir.iterdir()):
            # Prints the oldest log for the subdir.
            if subdir.is_dir():
                print_oldest_log(subdir, testing, since, level)


def print_oldest_log(path, testing, since, level):
    """
     Print the oldest log that matches the criteria. This is a wrapper around find_oldest_log that takes care of printing the file if it exists
     
     @param path - Path to the log file
     @param testing - True if we are testing False otherwise.
     @param since - Timestamp to start looking for logs. If None print all logs.
     @param level - Log level to print. Must be one of DEBUG INFO
    """
    path = find_oldest_log(path, testing)
    # Prints the log file at the given path.
    if path:
        print_log(path, since, level)
    else:
        print(f"No logfile found in {path}")


# main function for the main module
if __name__ == "__main__":
    main()
