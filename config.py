"""
AttendBot — Configuration
=========================
Environment variables, constants, and the Flask app instance.
"""

import os
from zoneinfo import ZoneInfo
from flask import Flask

from dotenv import load_dotenv
load_dotenv()

IST = ZoneInfo("Asia/Kolkata")

# ── Environment ──────────────────────────────────────────────────────────────
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS        = set(map(int, os.environ.get("ADMIN_IDS", "0").split(",")))  # Telegram user IDs
ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "")           # set via .env
WEBHOOK_URL      = os.environ.get("WEBHOOK_URL", "")  # e.g. https://yourapp.onrender.com
DATABASE_URL     = os.environ.get("DATABASE_URL", "")
LEAVES_PER_MONTH = 4

# Runtime-promoted admins (cleared on server restart — safe for evaluation)
ELEVATED_ADMINS: set[int] = set()

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Known patterns (used for routing + registration guard) ───────────────────
BUTTON_LABELS = {
    "✅ Mark Present", "Mark Present",
    "🏖️ Take Leave", "Take Leave",
    "📊 Check Balance", "Check Balance",
    "📋 Admin Report", "Admin Report",
    "📥 Export CSV", "Export CSV",
}

GREETINGS = {"hi", "hello", "hey", "hii", "hiii", "hola", "yo", "sup",
             "good morning", "good afternoon", "good evening", "gm", "namaste"}
THANKS = {"thanks", "thank you", "thankyou", "thx", "ty", "thank u"}
