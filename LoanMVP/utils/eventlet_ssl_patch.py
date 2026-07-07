"""Work around a longstanding eventlet bug: GreenSSLContext does not
override verify_mode/verify_flags/options, so CPython's own property
setter recurses into itself forever when called on a GreenSSLContext
instance ("RecursionError: maximum recursion depth exceeded" from
ssl.py's verify_mode setter). The setter resolves the class name
`SSLContext` via super(), and monkey-patching rebinds that name to
GreenSSLContext, so super() lands back on the same Python-level setter.
https://github.com/eventlet/eventlet/issues/371

Rebind the affected descriptors on GreenSSLContext straight to the
C-level _ssl._SSLContext getset descriptors. Those set the value
directly and can never re-enter the recursive Python-level property.

Must run AFTER eventlet has actually monkey-patched socket/ssl in the
process that will serve real requests. Under gunicorn, that's the
*worker* process, post-fork -- the arbiter (master) imports the app
to validate it before forking, but never monkey-patches. Since workers
are forked from the arbiter, they inherit the already-imported app
module from Python's module cache, so calling this only at import
time (module-level in app.py) runs once, in the arbiter, before
monkey-patching, and never runs again in the worker where it matters.
gunicorn.conf.py's post_fork hook calls this explicitly in the worker
after fork, which is the reliable call site; the app.py call remains
as a harmless fallback for non-gunicorn contexts (e.g. `flask` CLI
commands, which never monkey-patch at all).
"""
import logging

_log = logging.getLogger("ssl_recursion_patch")


def patch_eventlet_ssl_recursion():
    try:
        import eventlet.patcher

        # eventlet tracks ssl patching under the "socket" key, not "ssl".
        if not eventlet.patcher.is_monkey_patched("socket"):
            _log.warning("[ssl-patch] socket is not monkey-patched -- skipping, patch will not apply")
            return

        import _ssl
        import ssl as _ssl_module
        from eventlet.green import ssl as _green_ssl

        _log.warning(
            "[ssl-patch] socket is monkey-patched. ssl.SSLContext=%r GreenSSLContext=%r same=%s",
            _ssl_module.SSLContext, _green_ssl.GreenSSLContext,
            _ssl_module.SSLContext is _green_ssl.GreenSSLContext,
        )

        c_ssl_context = _ssl._SSLContext
        rebound = []

        def _rebind(prop_name):
            c_descriptor = getattr(c_ssl_context, prop_name, None)
            if c_descriptor is None:
                _log.warning("[ssl-patch] no C-level descriptor found for %s -- skipping", prop_name)
                return

            def _getter(self, _d=c_descriptor):
                return _d.__get__(self, c_ssl_context)

            def _setter(self, value, _d=c_descriptor):
                _d.__set__(self, value)

            setattr(_green_ssl.GreenSSLContext, prop_name, property(_getter, _setter))
            rebound.append(prop_name)

        for prop_name in ("verify_mode", "verify_flags", "options", "minimum_version", "maximum_version"):
            _rebind(prop_name)

        # Prove the fix actually works before trusting it in a real request:
        # construct a context the same way urllib3 does and set verify_mode.
        try:
            _test_ctx = _green_ssl.GreenSSLContext(_ssl_module.PROTOCOL_TLS_CLIENT)
            _test_ctx.verify_mode = _ssl_module.CERT_REQUIRED
            _log.warning("[ssl-patch] self-test passed -- rebound %s, verify_mode set OK", rebound)
        except RecursionError:
            _log.error("[ssl-patch] self-test FAILED -- verify_mode still recurses after patching %s", rebound)
    except Exception:
        _log.exception("[ssl-patch] setup raised an exception -- patch did not apply")
