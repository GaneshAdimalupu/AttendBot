#!/usr/bin/env python3
"""
run.py — Local dev runner.
Usage:  python run.py   (reads .env automatically)
"""
import os
from dotenv import load_dotenv
load_dotenv()

from bot import app, init_db

init_db()
port = int(os.environ.get("PORT", 5000))
print(f"\n🤖 AttendBot running on http://localhost:{port}")
print(f"📊 Dashboard: http://localhost:{port}/dashboard")
print(f"🌱 Seed demo: http://localhost:{port}/demo/seed\n")
app.run(host="0.0.0.0", port=port, debug=True)
