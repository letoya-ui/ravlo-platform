"""Gunicorn server hooks. Loaded automatically from the working directory --
no Start Command change needed.
"""


def post_worker_init(worker):
    """Runs in each worker process after the worker has finished
    initializing -- specifically, after the eventlet worker class's own
    init_process() has already called eventlet.monkey_patch(). This is
    the reliable place to apply fixes that depend on monkey-patching
    having actually happened in *this* process.

    post_fork fires too early for this: it runs immediately after fork,
    but BEFORE init_process()/monkey_patch() -- confirmed via production
    logs where our patch's own "not monkey-patched" skip message printed
    from post_fork, followed immediately after by eventlet's monkey-patch
    warnings, proving monkey_patch() hadn't run yet at that point.

    See utils/eventlet_ssl_patch.py for why calling this only at
    module-import time isn't enough in the first place: workers are
    forked from the arbiter, which imports the app (running any
    top-level code) before forking and before any monkey-patching
    occurs, so a one-shot import-time call runs too early and never
    gets a second chance in the process that actually serves requests.
    """
    from LoanMVP.utils.eventlet_ssl_patch import patch_eventlet_ssl_recursion
    patch_eventlet_ssl_recursion()
