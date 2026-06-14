"""
AttendBot — Routes
==================
All Flask route functions: webhook, dashboard, API, cron, setup, and demo seeding.
"""

import json, traceback, random
from datetime import date, datetime, timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo

from flask import request, jsonify, render_template
import requests

from config import (
    app, IST, TG_API, BOT_TOKEN, ADMIN_IDS, ADMIN_PASSWORD,
    WEBHOOK_URL, LEAVES_PER_MONTH, BUTTON_LABELS, GREETINGS, THANKS,
)
from database import execute_query
from helpers import (
    tg, send, now_ist, today_ist, time_greeting,
    is_weekend, is_holiday, get_holiday_desc, get_all_holidays,
    working_days_in_month,
    already_marked, register, is_registered, get_user_name, is_admin, mark,
    persistent_menu, sync_username,
)
from handlers import (
    handle_start, handle_direct_mark, handle_status,
    handle_whois, handle_remove, handle_archived, handle_restore,
    handle_addholiday, handle_removeholiday, handle_holidays,
    handle_broadcast, handle_rename, handle_report, handle_export,
    handle_callback_query, handle_admin_promote,
)


# ── Webhook endpoint ──────────────────────────────────────────────────────────
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.json
    try:
        if "callback_query" in update:
            handle_callback_query(update["callback_query"])

        if "message" in update:
            msg  = update["message"]
            text = msg.get("text","").strip()
            uid  = msg["from"]["id"]

            if not is_registered(uid):
                if text == "/start":
                    send(uid, "👋 Welcome to <b>AttendBot</b>!\n\nBefore we begin, please type your <b>Full Legal Name</b> as it should appear on official records:")
                elif text in BUTTON_LABELS or text.startswith("/"):
                    send(uid, "⚠️ <b>Not registered yet!</b>\n\nPlease type /start first to set up your profile.")
                else:
                    uname = msg["from"].get("username", "")
                    register(uid, text, uname)
                    send(uid, f"✅ Thank you, <b>{text}</b>! Your profile is set up.\n\nPlease use the menu below to update your status.", reply_markup=persistent_menu(uid))
                return jsonify(ok=True)

            # Auto-sync username on every interaction
            sync_username(msg)

            if text in ["/start", "/help"]:
                handle_start(msg)
            elif text in ["✅ Mark Present", "Mark Present"]:
                handle_direct_mark(msg, "present")
            elif text in ["🏖️ Take Leave", "Take Leave"]:
                handle_direct_mark(msg, "leave")
            elif text in ["📊 Check Balance", "Check Balance", "/status", "/leaves"]:
                handle_status(msg)
            elif text.startswith("📋 Admin Report") or text.startswith("Admin Report") or text.startswith("/report"):
                handle_report(msg)
            elif text.startswith("📥 Export CSV") or text.startswith("Export CSV") or text.startswith("/export"):
                handle_export(msg)
            elif text.startswith("/whois"):
                handle_whois(msg)
            elif text.startswith("/remove"):
                handle_remove(msg)
            elif text.startswith("/archived"):
                handle_archived(msg)
            elif text.startswith("/restore"):
                handle_restore(msg)
            elif text.startswith("/broadcast"):
                handle_broadcast(msg)
            elif text.startswith("/rename"):
                handle_rename(msg)
            elif text.startswith("/addholiday"):
                handle_addholiday(msg)
            elif text.startswith("/removeholiday"):
                handle_removeholiday(msg)
            elif text.startswith("/holidays") or text.startswith("/holiday"):
                handle_holidays(msg)
            elif text.startswith("/admin"):
                handle_admin_promote(msg)
            elif text.lower() in GREETINGS:
                name = get_user_name(uid)
                greeting = time_greeting()
                today = today_ist()
                status = already_marked(uid, today)
                if is_weekend(today):
                    nudge = "It's the weekend — enjoy your break! 🌴"
                elif status == "present":
                    nudge = "You're already marked present today. ✅"
                elif status == "leave":
                    nudge = "You're on leave today. Rest well! 🏖️"
                else:
                    nudge = "Don't forget to mark your attendance — tap a button below!"
                send(uid,
                    f"{greeting}, <b>{name}</b>! 👋\n\n{nudge}",
                    reply_markup=persistent_menu(uid)
                )
            elif text.lower() in THANKS:
                name = get_user_name(uid)
                send(uid,
                    f"You're welcome, <b>{name}</b>! Happy to help. 😊\n\n"
                    "Tap a button below if you need anything else.",
                    reply_markup=persistent_menu(uid)
                )
            else:
                name = get_user_name(uid)
                send(uid,
                    f"Sorry <b>{name}</b>, I didn't understand that.\n\n"
                    "Use the <b>buttons below</b> or try /help for a list of commands.",
                    reply_markup=persistent_menu(uid)
                )

    except Exception as e:
        traceback.print_exc()
    return jsonify(ok=True)


# ── Admin web dashboard ───────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/dashboard")
def api_dashboard():
    today = today_ist()
    year, month = today.year, today.month
    wdays_past = [d for d in working_days_in_month(year, month) if d <= today]

    employees = execute_query("SELECT * FROM employees WHERE is_active = TRUE ORDER BY name", fetch_all=True)
    month_str = f"{year:04d}-{month:02d}"
    all_att = execute_query(
        "SELECT telegram_id, date, status, marked_at FROM attendance "
        "WHERE to_char(date, 'YYYY-MM')=%s", (month_str,),
        fetch_all=True
    )

    att_map = {}
    for r in all_att:
        d_key = r["date"].isoformat() if hasattr(r["date"], 'isoformat') else r["date"]
        raw_ma = r.get("marked_at")
        if isinstance(raw_ma, datetime):
            if raw_ma.tzinfo is None:
                raw_ma = raw_ma.replace(tzinfo=ZoneInfo("UTC"))
            ma = raw_ma.astimezone(IST).isoformat()
        else:
            ma = raw_ma
        att_map[(r["telegram_id"], d_key)] = {"status": r["status"], "marked_at": ma}

    emp_data = []
    today_present = today_leave = today_unmarked = 0

    for emp in employees:
        tid = emp["telegram_id"]
        today_s = att_map.get((tid, today.isoformat()), {})
        today_status = today_s.get("status")
        today_time   = today_s.get("marked_at")
        if today_status == "present":  today_present += 1
        elif today_status == "leave":  today_leave += 1
        else:                          today_unmarked += 1

        present = sum(1 for d in wdays_past if att_map.get((tid, d.isoformat()),{}).get("status")=="present")
        leave   = sum(1 for d in wdays_past if att_map.get((tid, d.isoformat()),{}).get("status")=="leave")
        unmarked= len(wdays_past) - present - leave
        remain  = max(0, LEAVES_PER_MONTH - leave)

        daily = {}
        ddays_in_month = monthrange(year, month)[1]
        for dd in range(1, ddays_in_month + 1):
            ds = date(year, month, dd).isoformat()
            info = att_map.get((tid, ds), {})
            if info: daily[ds] = info["status"]

        emp_data.append({
            "name": emp["name"],
            "username": emp["username"] or "",
            "today_status": today_status,
            "today_time": today_time,
            "month": {
                "present": present, "leave": leave, "unmarked": unmarked,
                "leaves_remaining": remain, "daily": daily
            }
        })

    archived_employees = execute_query("SELECT * FROM employees WHERE is_active = FALSE ORDER BY name", fetch_all=True)
    archived_data = []
    for emp in archived_employees:
        archived_data.append({
            "telegram_id": emp["telegram_id"],
            "name": emp["name"],
            "username": emp["username"] or ""
        })

    today_holiday_desc = get_holiday_desc(today)
    return jsonify({
        "employees": emp_data,
        "archived": archived_data,
        "holidays": get_all_holidays(),
        "today": {
            "present": today_present, 
            "on_leave": today_leave, 
            "unmarked": today_unmarked,
            "is_weekend": is_weekend(today),
            "is_holiday": today_holiday_desc is not None,
            "holiday_desc": today_holiday_desc
        }
    })

@app.route("/api/admin/verify", methods=["POST"])
def api_verify_admin():
    data = request.json or {}
    password = data.get("password")
    if password == ADMIN_PASSWORD:
        return jsonify({"success": True})
    return jsonify({"error": "Unauthorized"}), 401

@app.route("/api/holidays/add", methods=["POST"])
def api_add_holiday():
    data = request.json or {}
    password = data.get("password")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 401
    
    start_date_str = data.get("date")
    end_date_str = data.get("end_date")
    description = data.get("description", "Holiday").strip()
    
    if not start_date_str:
        return jsonify({"error": "Missing date"}), 400
        
    try:
        start_d = date.fromisoformat(start_date_str)
    except ValueError:
        return jsonify({"error": "Invalid start date format (must be YYYY-MM-DD)"}), 400
        
    dates_to_add = [start_d]
    if end_date_str:
        try:
            end_d = date.fromisoformat(end_date_str)
        except ValueError:
            return jsonify({"error": "Invalid end date format (must be YYYY-MM-DD)"}), 400
            
        if end_d < start_d:
            return jsonify({"error": "End date must be after or equal to start date"}), 400
            
        delta = end_d - start_d
        for i in range(1, delta.days + 1):
            dates_to_add.append(start_d + timedelta(days=i))
            
    try:
        for d in dates_to_add:
            execute_query(
                "INSERT INTO holidays (date, description) VALUES (%s, %s) "
                "ON CONFLICT (date) DO UPDATE SET description=EXCLUDED.description",
                (d.isoformat(), description),
                commit=True
            )
        return jsonify({"success": True, "count": len(dates_to_add), "description": description})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/holidays/delete", methods=["POST"])
def api_delete_holiday():
    data = request.json or {}
    password = data.get("password")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 401
        
    date_str = data.get("date")
    if not date_str:
        return jsonify({"error": "Missing date"}), 400
        
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400
        
    try:
        execute_query("DELETE FROM holidays WHERE date=%s", (d.isoformat(),), commit=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({"status": "ok", "bot": "AttendBot", "dashboard": "/dashboard"})

@app.route("/setup")
def setup():
    if not WEBHOOK_URL:
        return jsonify({"error": "WEBHOOK_URL not set"})

    results = {}

    # 1. Set webhook
    r = requests.post(f"{TG_API}/setWebhook",
                      json={"url": f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"})
    results["webhook"] = r.json()

    # 2. Register command menu (the "/" button in chat)
    commands = [
        {"command": "start",     "description": "Show welcome message & help"},
        {"command": "status",    "description": "View your monthly attendance"},
        {"command": "leaves",    "description": "Check remaining leave balance"},
        {"command": "rename",    "description": "Change your display name"},
        {"command": "report",    "description": "[Admin] Team report — /report [month]"},
        {"command": "export",    "description": "[Admin] Export CSV — /export [month]"},
        {"command": "whois",     "description": "[Admin] Look up an employee"},
        {"command": "remove",    "description": "[Admin] Archive an employee"},
        {"command": "archived",  "description": "[Admin] View archived employees"},
        {"command": "restore",   "description": "[Admin] Restore an archived employee"},
        {"command": "broadcast", "description": "[Admin] Message all employees"},
        {"command": "holidays",      "description": "List holidays for the year"},
        {"command": "addholiday",    "description": "[Admin] Add holiday — /addholiday YYYY-MM-DD Desc"},
        {"command": "removeholiday", "description": "[Admin] Remove holiday — /removeholiday YYYY-MM-DD"},
        {"command": "help",      "description": "Show available commands"},
    ]
    r = requests.post(f"{TG_API}/setMyCommands", json={"commands": commands})
    results["commands"] = r.json()

    # 3. Set bot description (shown before user taps Start)
    description = (
        "\ud83d\udccb AttendBot \u2014 One-tap daily attendance.\n\n"
        "Mark present or leave with a single tap. "
        "Track your streaks, leave balance, and monthly stats. "
        "Admins get a live dashboard, CSV exports, and team reports."
    )
    r = requests.post(f"{TG_API}/setMyDescription", json={"description": description})
    results["description"] = r.json()

    # 4. Set short description (shown in chat list / sharing)
    r = requests.post(f"{TG_API}/setMyShortDescription",
                      json={"short_description": "One-tap attendance tracking for teams"})
    results["short_description"] = r.json()

    return jsonify(results)


# ── Daily Reminder Endpoint ──────────────────────────────────────────────────
@app.route("/cron/remind")
def cron_remind():
    today = today_ist()
    if is_weekend(today) or is_holiday(today):
        return jsonify({"skipped": "weekend_or_holiday"})

    employees = execute_query("SELECT telegram_id, name FROM employees WHERE is_active = TRUE", fetch_all=True)
    marked_today_rows = execute_query(
        "SELECT telegram_id FROM attendance WHERE date=%s",
        (today.isoformat(),), fetch_all=True
    )

    if not employees:
        return jsonify({"reminded": 0, "total": 0})

    marked_today = {r["telegram_id"] for r in marked_today_rows} if marked_today_rows else set()
    greeting = time_greeting()

    reminded = 0
    for emp in employees:
        if emp["telegram_id"] not in marked_today:
            send(emp["telegram_id"],
                f"{greeting}, <b>{emp['name']}</b>!\n\n"
                f"<b>{today.strftime('%A, %d %B %Y')}</b>\n\n"
                "Don't forget to mark your attendance — just tap a button below:",
                reply_markup=persistent_menu(emp["telegram_id"])
            )
            reminded += 1

    return jsonify({"reminded": reminded, "total": len(employees), "already_marked": len(marked_today)})


# ── Demo Seeding ─────────────────────────────────────────────────────────────
@app.route("/demo/seed")
def seed_demo():
    demo_employees = [
        (1001, "Arun Kumar",    "arunkumar"),
        (1002, "Priya Menon",   "priyamenon"),
        (1003, "Rahul Nair",    "rahulnair"),
        (1004, "Sneha Thomas",  "snehathomas"),
        (1005, "Vijay Pillai",  "vijaypillai"),
        (1006, "Lakshmi Devi",  "lakshmidevi"),
        (1007, "Anoop Krishnan","anoopk"),
        (1008, "Meera Raj",     "meeraraj"),
        (1009, "Siddharth V",   "sidv"),
        (1010, "Divya George",  "divyag"),
    ]
    today = today_ist()
    year, month = today.year, today.month
    wdays = [d for d in working_days_in_month(year, month) if d <= today]

    # Use our built-in helper functions (which auto-commit to PostgreSQL!)
    for tid, name, uname in demo_employees:
        register(tid, name, uname)
        
    for d in wdays:
        for tid, _, _ in demo_employees:
            if random.random() < 0.05: continue  # ~5% chance of not marking
            status = "leave" if random.random() < 0.12 else "present"
            mark(tid, d, status)

    return jsonify({"seeded": len(demo_employees), "days": len(wdays)})
