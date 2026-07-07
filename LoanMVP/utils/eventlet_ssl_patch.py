"""Work around a longstanding eventlet bug: CPython's ssl.py implements
SSLContext.verify_mode (and verify_flags/options/minimum_version/
maximum_version) as a property whose setter does
`super(SSLContext, SSLContext).verify_mode.__set__(self, value)` --
resolving the name `SSLContext` fresh from ssl.py's own module globals
on every call. Eventlet's monkey-patching reassigns that global name to
GreenSSLContext, so the setter's super() call resolves to
`super(GreenSSLContext, GreenSSLContext)` regardless of what class the
instance actually is. If GreenSSLContext doesn't override the property
itself, that resolves back to the very setter currently executing,
recursing forever ("RecursionError: maximum recursion depth exceeded").
https://github.com/eventlet/eventlet/issues/371

This needs patching on TWO classes, not just GreenSSLContext:

1. GreenSSLContext itself -- for any code that resolves `ssl.SSLContext`
   fresh (via attribute access) after monkey-patching; it gets
   GreenSSLContext and instantiates that directly.

2. The ORIGINAL ssl.SSLContext class (GreenSSLContext's own base class)
   -- for code like urllib3, which does `from ssl import SSLContext` at
   its own import time. That's a one-time name binding, immune to
   monkey-patching's later reassignment of ssl.SSLContext -- it keeps
   pointing at the original class forever. Under gunicorn, this bites
   hard: the arbiter (master) process imports the whole app -- including
   urllib3 -- to validate it BEFORE forking any workers, and the arbiter
   itself never monkey-patches. Workers are forked from the arbiter, so
   they inherit urllib3's already-captured original-class reference via
   Python's module cache. The worker's own eventlet.monkey_patch() call
   (in its init_process()) reassigns ssl.SSLContext going forward, but
   can't retroactively fix urllib3's already-bound name. Confirmed by
   reproducing this exact scenario locally: importing urllib3.util.ssl_
   before monkey_patch() runs recurses when creating a context via
   urllib3's own create_urllib3_context() and setting a property on it
   -- and patching only GreenSSLContext does NOT fix it, because
   type(context) is the original SSLContext class, not GreenSSLContext.
   Patching the original class directly does fix it.

Rebind the affected descriptors straight to the C-level
_ssl._SSLContext getset descriptors. Those set the value directly and
can never re-enter the recursive Python-level property.

Must run AFTER eventlet has actually monkey-patched socket/ssl in the
process that will serve real requests. Under gunicorn, that's inside
the worker, after its own init_process() has run -- gunicorn.conf.py's
post_worker_init hook (not post_fork, which fires too early, before
init_process()/monkey_patch()) calls this explicitly; the app.py call
remains as a harmless fallback for non-gunicorn contexts (e.g. `flask`
CLI commands, which never monkey-patch at all).
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

        original_ssl_context = _green_ssl.GreenSSLContext.__bases__[0]

        _log.warning(
            "[ssl-patch] socket is monkey-patched. ssl.SSLContext=%r GreenSSLContext=%r "
            "original(base)=%r same_as_green=%s",
            _ssl_module.SSLContext, _green_ssl.GreenSSLContext, original_ssl_context,
            _ssl_module.SSLContext is _green_ssl.GreenSSLContext,
        )

        c_ssl_context = _ssl._SSLContext
        rebound = []

        def _rebind(cls, prop_name):
            c_descriptor = getattr(c_ssl_context, prop_name, None)
            if c_descriptor is None:
                _log.warning("[ssl-patch] no C-level descriptor found for %s -- skipping", prop_name)
                return

            def _getter(self, _d=c_descriptor):
                return _d.__get__(self, c_ssl_context)

            def _setter(self, value, _d=c_descriptor):
                _d.__set__(self, value)

            setattr(cls, prop_name, property(_getter, _setter))
            rebound.append((cls.__name__, prop_name))

        for prop_name in ("verify_mode", "verify_flags", "options", "minimum_version", "maximum_version"):
            _rebind(_green_ssl.GreenSSLContext, prop_name)
            if original_ssl_context is not _green_ssl.GreenSSLContext:
                _rebind(original_ssl_context, prop_name)

        # Prove the fix actually works before trusting it in a real request --
        # test both the green class AND the original class (the one urllib3
        # actually uses via its own captured `from ssl import SSLContext`).
        try:
            _test_green = _green_ssl.GreenSSLContext(_ssl_module.PROTOCOL_TLS_CLIENT)
            _test_green.verify_mode = _ssl_module.CERT_REQUIRED
            _test_original = original_ssl_context(_ssl_module.PROTOCOL_TLS_CLIENT)
            _test_original.verify_mode = _ssl_module.CERT_REQUIRED
            _log.warning("[ssl-patch] self-test passed -- rebound %s", rebound)
        except RecursionError:
            _log.error("[ssl-patch] self-test FAILED -- verify_mode still recurses after patching %s", rebound)
    except Exception:
        _log.exception("[ssl-patch] setup raised an exception -- patch did not apply")
