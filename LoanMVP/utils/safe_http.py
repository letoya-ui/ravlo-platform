"""Run outbound HTTPS calls off the eventlet greenlet stack.

Under gunicorn's eventlet worker, requests/urllib3 calls through eventlet's
monkey-patched ssl module can hit a longstanding recursion bug
(https://github.com/eventlet/eventlet/issues/371), surfacing as
"RecursionError: maximum recursion depth exceeded while calling a Python
object" from otherwise-correct code. Running the blocking call in eventlet's
native-thread pool avoids the patched SSL path for that call. In non-eventlet
environments (dev/local), this just calls the function directly.
"""

def _eventlet_active() -> bool:
    try:
        import eventlet.patcher
    except ImportError:
        return False
    return eventlet.patcher.is_monkey_patched("socket")


def safe_call(func, *args, **kwargs):
    """Call func(*args, **kwargs), routing through eventlet.tpool if active."""
    if _eventlet_active():
        import eventlet.tpool
        return eventlet.tpool.execute(func, *args, **kwargs)
    return func(*args, **kwargs)
