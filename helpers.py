"""
AttendBot — Helpers
===================
Telegram API wrappers, date/time utilities, holiday logic,
attendance calculations, UI builders, and utility functions.
"""

import os, json, re, calendar
from datetime import date, datetime, timedelta
from calendar import monthrange

import requests

from config import (
    IST, TG_API, ADMIN_IDS, ADMIN_PASSWORD, ELEVATED_ADMINS,
    LEAVES_PER_MONTH, WEBHOOK_URL,
)
from database import execute_query


# ── Telegram helpers ──────────────────────────────────────────────────────────
def tg(method, **kwargs):
    resp = requests.post(f"{TG_API}/{method}", json=kwargs, timeout=10)
    return resp.json()

def send(chat_id, text, **kwargs):
    return tg("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", **kwargs)


# ── Date / time ──────────────────────────────────────────────────────────────
def now_ist() -> datetime:
    return datetime.now(IST)

def today_ist() -> date:
    return now_ist().date()

def time_greeting() -> str:
    hour = now_ist().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    return "Good evening"

def is_weekend(d: date) -> bool:
    return d.weekday() >= 5   # Saturday=5, Sunday=6


# ── Holiday logic ────────────────────────────────────────────────────────────
def is_holiday(d: date) -> bool:
    row = execute_query("SELECT 1 FROM holidays WHERE date=%s", (d.isoformat(),), fetch_one=True)
    return row is not None

def get_holiday_desc(d: date) -> str | None:
    row = execute_query("SELECT description FROM holidays WHERE date=%s", (d.isoformat(),), fetch_one=True)
    return row["description"] if row else None

def get_holidays_in_month(year: int, month: int) -> set[date]:
    rows = execute_query(
        "SELECT date FROM holidays WHERE to_char(date, 'YYYY-MM')=%s",
        (f"{year:04d}-{month:02d}",),
        fetch_all=True
    )
    if not rows:
        return set()
    res = set()
    for r in rows:
        d = r["date"]
        if isinstance(d, str):
            res.add(date.fromisoformat(d))
        elif isinstance(d, date):
            res.add(d)
    return res

def get_all_holidays() -> list[dict]:
    rows = execute_query(
        "SELECT date, description FROM holidays ORDER BY date ASC",
        fetch_all=True
    )
    if not rows:
        return []
    res = []
    for r in rows:
        d = r["date"]
        d_str = d.isoformat() if isinstance(d, date) else str(d)
        res.append({"date": d_str, "description": r["description"]})
    return res

def working_days_in_month(year: int, month: int):
    days_in_month = monthrange(year, month)[1]
    holidays_set = get_holidays_in_month(year, month)
    return [date(year, month, d) for d in range(1, days_in_month + 1)
            if not is_weekend(date(year, month, d)) and date(year, month, d) not in holidays_set]


# ── Attendance calculations ──────────────────────────────────────────────────
def leave_count(telegram_id: int, year: int, month: int) -> int:
    row = execute_query(
        "SELECT COUNT(*) AS n FROM attendance "
        "WHERE telegram_id=%s AND status='leave' "
        "AND to_char(date, 'YYYY-MM')=%s",
        (telegram_id, f"{year:04d}-{month:02d}"),
        fetch_one=True
    )
    return row["n"]

def already_marked(telegram_id: int, d: date) -> str | None:
    row = execute_query(
        "SELECT status FROM attendance WHERE telegram_id=%s AND date=%s",
        (telegram_id, d.isoformat()),
        fetch_one=True
    )
    return row["status"] if row else None

def mark(telegram_id: int, d: date, status: str):
    now_ist_val = datetime.now(IST)
    execute_query(
        "INSERT INTO attendance(telegram_id, date, status, marked_at) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (telegram_id, date) DO UPDATE SET status=EXCLUDED.status, marked_at=EXCLUDED.marked_at",
        (telegram_id, d.isoformat(), status, now_ist_val),
        commit=True
    )

def register(telegram_id: int, name: str, username: str):
    execute_query(
        "INSERT INTO employees(telegram_id, name, username, is_active) VALUES (%s,%s,%s, TRUE) "
        "ON CONFLICT (telegram_id) DO UPDATE SET name=EXCLUDED.name, username=EXCLUDED.username, is_active=TRUE",
        (telegram_id, name, username or ""),
        commit=True
    )

def is_registered(telegram_id: int) -> bool:
    row = execute_query(
        "SELECT 1 FROM employees WHERE telegram_id=%s AND is_active=TRUE",
        (telegram_id,),
        fetch_one=True
    )
    return row is not None

def get_user_name(telegram_id: int) -> str:
    row = execute_query(
        "SELECT name FROM employees WHERE telegram_id=%s",
        (telegram_id,),
        fetch_one=True
    )
    return row["name"] if row else "Employee"

def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS or telegram_id in ELEVATED_ADMINS

def get_streak(telegram_id: int) -> int:
    today = today_ist()
    streak = 0
    d = today
    while True:
        if is_weekend(d):
            d -= timedelta(days=1)
            continue
        row = execute_query(
            "SELECT status FROM attendance WHERE telegram_id=%s AND date=%s",
            (telegram_id, d.isoformat()),
            fetch_one=True
        )
        if row and row["status"] == "present":
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak

def attendance_rate(telegram_id: int, year: int, month: int):
    """Return (user_rate%, team_avg%) for the month so far."""
    today = today_ist()
    wdays_past = [d for d in working_days_in_month(year, month) if d <= today]
    total_wd = len(wdays_past)
    if total_wd == 0:
        return 0.0, 0.0

    user_present = execute_query(
        "SELECT COUNT(*) AS n FROM attendance "
        "WHERE telegram_id=%s AND status='present' AND to_char(date, 'YYYY-MM')=%s",
        (telegram_id, f"{year:04d}-{month:02d}"), fetch_one=True
    )["n"]
    user_rate = round((user_present / total_wd) * 100, 1)

    employees = execute_query("SELECT COUNT(*) AS n FROM employees WHERE is_active = TRUE", fetch_one=True)["n"]
    if employees == 0:
        return user_rate, 0.0

    team_present = execute_query(
        "SELECT COUNT(*) AS n FROM attendance "
        "WHERE status='present' AND to_char(date, 'YYYY-MM')=%s",
        (f"{year:04d}-{month:02d}",), fetch_one=True
    )["n"]
    team_rate = round((team_present / (total_wd * employees)) * 100, 1)
    return user_rate, team_rate

def is_late_mark() -> bool:
    return now_ist().hour >= 11


# ── UI builders ──────────────────────────────────────────────────────────────
def persistent_menu(telegram_id: int):
    keyboard = [
        [{"text": "✅ Mark Present"}, {"text": "🏖️ Take Leave"}],
        [{"text": "📊 Check Balance"}]
    ]
    if is_admin(telegram_id):
        keyboard.append([{"text": "📋 Admin Report"}, {"text": "📥 Export CSV"}])
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "is_persistent": True
    }

MILESTONES = {50, 25, 20, 15, 10, 5}

def streak_text(streak: int) -> str:
    if streak == 0:
        return ""
    if streak in MILESTONES:
        return (
            f"\n\n🎉 <b>MILESTONE — {streak}-day streak!</b>\n"
            "You're one of the most consistent members. Keep going!"
        )
    if streak >= 10:
        return f"\n\n🔥 <b>{streak}-day streak!</b> Incredible dedication!"
    if streak >= 5:
        return f"\n\n🔥 <b>{streak}-day streak!</b> Keep it going!"
    return f"\n\n🔥 Streak: {streak} days"

def leave_bar(remaining: int) -> str:
    used = LEAVES_PER_MONTH - remaining
    return "🟩" * remaining + "⬜" * used


# ── Month argument parser ───────────────────────────────────────────────────
def parse_month_arg(text: str, command: str):
    """
    Parse an optional month from a command string.
    Supported formats (case-insensitive):
      /export                 → current month
      /export last            → previous month
      /export May             → May of current year
      /export May 2025        → May 2025
      /export 2025-05         → May 2025
      /export 05/2025         → May 2025
    Returns (year, month) integers.
    """
    today = today_ist()
    arg = text[len(command):].strip().lower()

    if not arg or arg in ("now", "current", "this", "this month"):
        return today.year, today.month

    if arg in ("last", "prev", "previous", "last month"):
        first = date(today.year, today.month, 1)
        prev = first - timedelta(days=1)
        return prev.year, prev.month

    # Try YYYY-MM
    m = re.match(r'^(\d{4})-(\d{1,2})$', arg)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Try MM/YYYY or MM-YYYY
    m = re.match(r'^(\d{1,2})[/-](\d{4})$', arg)
    if m:
        return int(m.group(2)), int(m.group(1))

    # Try month name ("may", "may 2025", "may, 2025")
    month_names = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    month_abbrs = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}
    parts = re.split(r'[\s,]+', arg)
    month_num = month_names.get(parts[0]) or month_abbrs.get(parts[0])
    if month_num:
        year = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else today.year
        return year, month_num

    return None, None  # unrecognised


# ── Username sync ────────────────────────────────────────────────────────────
def sync_username(msg):
    """Silently update the stored username if it has changed."""
    uid = msg["from"]["id"]
    current_uname = msg["from"].get("username", "")
    if not current_uname:
        return
    stored = execute_query(
        "SELECT username FROM employees WHERE telegram_id=%s",
        (uid,), fetch_one=True
    )
    if stored and stored["username"] != current_uname:
        execute_query(
            "UPDATE employees SET username=%s WHERE telegram_id=%s",
            (current_uname, uid), commit=True
        )
