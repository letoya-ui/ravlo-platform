# run.py — LoanMVP Production Launcher
import os
from datetime import datetime
from LoanMVP.app import create_app

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"LoanMVP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

def log(message):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line)
    with open(log_file, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")

def start_server():
    app = create_app()
    port = int(os.environ.get("PORT", 5050))
    host = os.environ.get("HOST", "0.0.0.0")
    async_mode = app.config.get("SOCKETIO_ASYNC_MODE", "threading")
    debug = bool(app.debug)

    log(f"Starting Ravlo on {host}:{port} using Socket.IO async mode '{async_mode}'")
    app.socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )

if __name__ == "__main__":
    start_server()
