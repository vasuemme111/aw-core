from pathlib import Path
from datetime import datetime
from typing import Optional


LOGLEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def print_log(
    
    path: Path, since: Optional[datetime] = None, level: Optional[str] = None
):
    """
     Print log from path to stdout. This is a helper function for : func : ` pycassa. util. print_log `
     
     @param path - Path to the log file
     @param since - If specified only print logs since this date.
     @param level - If specified only print logs with this level.
     
     @return Number of lines printed to stdout ( 0 means no lines printed at all ). If level is specified only print logs that match the
    """
    # Returns true if the path is a file.
    if not path.is_file():
        return

    show_levels = LOGLEVELS[LOGLEVELS.index(level) :] if level else None

    lines_printed = 0
    with path.open("r") as f:
        lines = f.readlines()
        print(f"Logs for module {path.parent.name} ({path.name}, {len(lines)} lines)")
        # Prints the lines of the file.
        for line in lines:
            # This function will skip lines that are less than the given date.
            if since:
                try:
                    linedate = datetime.strptime(line.split(" ")[0], "%Y-%m-%d")
                except ValueError:
                    # Could not parse the date, so skip this line
                    # NOTE: Just because the date could not be parsed, doesn't mean there isn't meaningful info there.
                    #       Would be better to find the first line after the cutoff, and then just print everything past that.
                    continue
                # Skip lines before the date
                # If linedate is less than since or less than since
                if linedate < since:
                    continue
            # If level is not in show_levels return false.
            if level:
                # If any level in show_levels is not in line
                if not any(level in line for level in show_levels):
                    continue
            print(line, end="")
            lines_printed += 1

    print(f"  (Filtered {lines_printed}/{len(lines)} lines)")


def find_oldest_log(path: Path, testing=False) -> Path:
    """
     Find the oldest log file in a directory. This is used to ensure that we don't accidentally get a file that's older than the one we're looking for
     
     @param path - The path to search for the oldest log file
     @param testing - If True we want to search for the test log instead of the normal log
     
     @return The oldest log file or None if there are no logs in the directory or the file does not end
    """
    # Returns the path to the directory if it s a directory.
    if not path.is_dir():
        return

    logfiles = [
        f
        for f in path.iterdir()
        if f.is_file()
        and f.name.endswith(".log")
        and ("testing" in f.name if testing else "testing" not in f.name)
    ]
    # Return true if logfiles are not logged.
    if not logfiles:
        return

    logfiles.sort(key=lambda f: f.stat().st_mtime)
    logfile = logfiles[-1]
    return logfile
