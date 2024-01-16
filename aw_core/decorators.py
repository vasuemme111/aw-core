import functools
import logging
import time
import warnings


def deprecated(f):  # pragma: no cover
    """
     Mark a function as deprecated. This is a decorator which can be used to mark functions as deprecated. It will result in a warning being emitted when the function is used.
     
     @param f - The function to be marked as deprecated. Must be a function.
     
     @return A function which when called will emit a warning when the function is used. Example :. @deprecated def foo ( a b
    """
    # Warn only once per deprecated function
    warned_for = False

    @functools.wraps(f)
    def g(*args, **kwargs):
        """
         Wrapper for deprecated functions. This is a function that will be called with the arguments passed to it and the keyword arguments passed to it.
         
         
         @return result of f ( * args ** kwargs ) or None if there was no result to return to the
        """
        # TODO: Use logging module instead?
        nonlocal warned_for
        # This function is deprecated. It is deprecated.
        if not warned_for:
            warnings.simplefilter("always", DeprecationWarning)  # turn off filter
            warnings.warn(
                "Call to deprecated function {}, "
                "this warning will only show once per function.".format(f.__name__),
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter("default", DeprecationWarning)  # reset filter
            warned_for = True
        return f(*args, **kwargs)

    return g


def restart_on_exception(f, delay=1, exception=Exception):  # pragma: no cover
    """
     Restart a function if an exception occurs. This is a decorator for functions that take a long time to execute.
     
     @param f - The function to be restarted. It will be called repeatedly until it returns True
     @param delay - The time in seconds to wait between restarts.
     @param exception - The exception to catch. Default is Exception.
     
     @return A function that will restart the function after a delay if an exception occurs. Example :. def test_exception_recover ( self ) : print ( " CREDIT! "
    """
    @functools.wraps(f)
    def g(*args, **kwargs):
        """
         Wrapper for restarting the function if there is an exception. Arguments : args : Positional arguments to pass to the function
        """
        # Run the function f with arguments args kwargs and sleeps for delays.
        while True:
            try:
                f(*args, **kwargs)
            except exception as e:
                # TODO: Use warnings module instead?
                logging.error(f"{f.__name__} crashed due to exception, restarting.")
                logging.error(e)
                time.sleep(
                    delay
                )  # To prevent extremely fast restarts in case of bad state.

    return g
