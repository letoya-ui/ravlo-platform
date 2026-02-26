import importlib
import pkgutil
import os
import inspect
from flask import Blueprint
from datetime import datetime


def log_message(message: str):
    """Write blueprint registration messages to a log file."""
    log_dir = os.path.join(os.path.dirname(__file__), "instance")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "blueprint_log.txt")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)


def register_all_blueprints(app):
    """
    Dynamically scan LoanMVP/routes for any Blueprint objects
    and register them automatically with Flask.
    """
    # ✅ Find the /routes/ folder (this is the real one)
    base_dir = os.path.dirname(__file__)
    package_path = os.path.join(base_dir, "routes")
    package_name = "LoanMVP.routes"

    # Check if the /routes folder actually exists
    if not os.path.exists(package_path):
        log_message("⚠️ Could not find 'routes' folder — fallback to current dir.")
        package_path = base_dir

    log_message(f"🔍 Scanning for blueprints in: {package_path}")
    total, success, failed = 0, 0, 0

    for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
        if is_pkg or module_name.startswith("__"):
            continue
        total += 1
        try:
            module = importlib.import_module(f"{package_name}.{module_name}")
            found = False

            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Blueprint):
                    app.register_blueprint(obj)
                    log_message(f"✅ Registered blueprint: {name} → {module_name}")
                    success += 1
                    found = True

            if not found:
                log_message(f"⚠️ No Blueprint object found in {module_name}")

        except Exception as e:
            log_message(f"❌ Failed to load {module_name}: {e}")
            failed += 1

    log_message(f"\n📊 Summary: {success}/{total} blueprints registered ({failed} failed).\n")
