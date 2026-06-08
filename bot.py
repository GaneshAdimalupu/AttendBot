"""
TinkerHub Attendance Bot
========================
A Telegram bot for frictionless daily attendance marking.
Upgraded with a Persistent Reply Keyboard for zero-friction UX.
Admins get full visibility via the web dashboard.

This file is the entrypoint — it wires together all modules and
re-exports `app` and `init_db` so that `run.py` and `Procfile`
continue to work unchanged.
"""

from config import app          # noqa: F401  — Flask app instance
from database import init_db    # noqa: F401  — DB schema initialiser
import routes                   # noqa: F401  — registers all @app.route handlers

init_db()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)