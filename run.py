# run.py — LoanMVP Production Launcher
import os
import sys
import time
import threading
from datetime import datetime
from LoanMVP.app import create_app

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"LoanMVP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

def log(msg):
    message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(message)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def start_server():
    app = create_app()

    # Render requires binding to the PORT environment variable
    port = int(os.environ.get("PORT", 5050))

    log(f" Starting LoanMVP Flask-SocketIO server on port {port} (threading mode)...")

    try:
        app.socketio.run(
            app,
            host="0.0.0.0",
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True  # Required for threading mode in production
        )
    except Exception as e:
        log(f" Server failed: {e}")
        time.sleep(5)

if __name__ == "__main__":
    log(" Initializing LoanMVP Production Service...")

    # Start the server in the main thread (Render prefers this)
    # but keep your threading model intact
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        log(" LoanMVP service stopped manually.")
        sys.exit(0)
