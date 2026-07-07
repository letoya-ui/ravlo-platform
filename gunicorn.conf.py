"""Gunicorn server hooks. Loaded automatically from the working directory --
no Start Command change needed.
"""


def post_fork(server, worker):
    """Runs in each worker process, right after fork and after gunicorn's
    eventlet worker class has called eventlet.monkey_patch() -- the
    reliable place to apply fixes that depend on monkey-patching having
    actually happened in *this* process. See utils/eventlet_ssl_patch.py
    for why calling this only at module-import time isn't enough: workers
    are forked from the arbiter, which imports the app (running any
    top-level code) before forking and before any monkey-patching occurs,
    so a one-shot import-time call runs too early and never gets a second
    chance in the process that actually serves requests.
    """
    from LoanMVP.utils.eventlet_ssl_patch import patch_eventlet_ssl_recursion
    patch_eventlet_ssl_recursion()
