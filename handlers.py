"""
AttendBot — Handlers
====================
All Telegram command and callback handlers.
"""

import os, json, re
from datetime import date, datetime, timedelta
from calendar import monthrange

import requests

from config import (
    IST, TG_API, ADMIN_IDS, ADMIN_PASSWORD, ELEVATED_ADMINS,
    LEAVES_PER_MONTH, WEBHOOK_URL,
)
from database import execute_query
from helpers import (
    tg, send, now_ist, today_ist, time_greeting,
    is_weekend, is_holiday, get_holiday_desc, get_holidays_in_month,
    get_all_holidays, working_days_in_month,
    leave_count, already_marked, mark, register, is_registered,
    get_user_name, is_admin, get_streak, attendance_rate, is_late_mark,
    persistent_menu, streak_text, leave_bar, parse_month_arg,
)

def handle_start(msg):
    uid = msg["from"]["id"]
    name = get_user_name(uid)
    greeting = time_greeting()

    admin_help = ""
    if is_admin(uid):
        admin_help = (
            "\n\n<b>Admin Commands:</b>\n"
            "• /whois <i>name</i> — look up an employee\n"
            "• /broadcast <i>message</i> — message everyone\n"
        )

    send(uid,
        f"{greeting}, <b>{name}</b>! Welcome back to <b>AttendBot</b>.\n\n"
        "Use the menu below — it only takes <b>one tap</b> to mark attendance!\n\n"
        "• <b>Mark Present</b> — mark yourself present\n"
        "• <b>Take Leave</b> — mark a leave day\n"
        "• <b>Check Balance</b> — view your monthly stats\n"
        "• /rename <i>New Name</i> — update your display name"
        + admin_help + "\n\n"
        "Just tap below:",
        reply_markup=persistent_menu(uid)
    )

def handle_direct_mark(msg, status: str):
    uid = msg["from"]["id"]
    today = today_ist()
    
    if is_weekend(today):
        send(uid, "It's a weekend — no attendance needed.\nEnjoy your break! See you on Monday.",
             reply_markup=persistent_menu(uid))
        return

    if is_holiday(today):
        desc = get_holiday_desc(today)
        holiday_name = f" ({desc})" if desc else ""
        send(uid, f"🎉 Today is a public holiday{holiday_name}! No attendance needed.\nEnjoy your day off! 🌴",
             reply_markup=persistent_menu(uid))
        return

    current = already_marked(uid, today)

    if current == status:
        word  = "Present" if status == "present" else "On Leave"
        used   = leave_count(uid, today.year, today.month)
        remain = max(0, LEAVES_PER_MONTH - used)
        streak = get_streak(uid) if status == "present" else 0
        send(uid,
            f"<b>{today.strftime('%A, %d %B %Y')}</b>\n\n"
            f"You're already marked <b>{word}</b> today!\n"
            f"No changes needed.\n\n"
            f"{leave_bar(remain)}\n"
            f"Leaves remaining: <b>{remain}</b> / {LEAVES_PER_MONTH}"
            + streak_text(streak),
            reply_markup=persistent_menu(uid))
        return

    if status == "leave":
        used = leave_count(uid, today.year, today.month)
        if current != "leave" and used >= LEAVES_PER_MONTH:
            send(uid,
                f"Cannot mark Leave — you've used all <b>{LEAVES_PER_MONTH}</b> leaves this month.\n\n"
                f"{leave_bar(0)}\n"
                "Contact your admin if you need more.",
                reply_markup=persistent_menu(uid))
            return

    switched = current is not None and current != status
    old_word = "Present" if current == "present" else "On Leave" if current else None

    mark(uid, today, status)

    used   = leave_count(uid, today.year, today.month)
    remain = max(0, LEAVES_PER_MONTH - used)
    status_word = "Present" if status == "present" else "On Leave"
    streak = get_streak(uid) if status == "present" else 0
    late_note = " <i>(marked late)</i>" if is_late_mark() else ""

    if switched:
        header = f"Switched from <b>{old_word}</b> → <b>{status_word}</b>{late_note}"
    else:
        header = f"<b>Marked as {status_word}</b>{late_note}"

    send(uid,
        f"<b>{today.strftime('%A, %d %B %Y')}</b>\n\n"
        f"{header}\n\n"
        f"{leave_bar(remain)}\n"
        f"Leaves remaining: <b>{remain}</b> / {LEAVES_PER_MONTH}"
        + streak_text(streak),
        reply_markup=persistent_menu(uid)
    )

def handle_status(msg):
    uid = msg["from"]["id"]
    today  = today_ist()
    year, month = today.year, today.month
    wdays  = working_days_in_month(year, month)
    days_in_month = monthrange(year, month)[1]
    all_days = [date(year, month, d) for d in range(1, days_in_month + 1)
                if not is_weekend(date(year, month, d))]

    rows = execute_query(
        "SELECT date, status FROM attendance WHERE telegram_id=%s "
        "AND to_char(date, 'YYYY-MM')=%s ORDER BY date",
        (uid, f"{year:04d}-{month:02d}"),
        fetch_all=True
    )

    marked = {r["date"].isoformat() if hasattr(r["date"], 'isoformat') else r["date"]: r["status"] for r in rows}
    lines  = []
    for d in all_days:
        ds = d.isoformat()
        h_desc = get_holiday_desc(d)
        if h_desc is not None:
            icon = f"🎉 Holiday ({h_desc})"
        elif d > today:
            icon = "➖"
        else:
            icon = {"present": "🟢", "leave": "🟠"}.get(marked.get(ds), "⚪")
        highlight = " ◀️ <i>Today</i>" if d == today else ""
        lines.append(f"<code>{d.strftime('%d %b %a')}</code>  {icon}{highlight}")

    total_p = sum(1 for v in marked.values() if v == "present")
    total_l = sum(1 for v in marked.values() if v == "leave")
    remain  = max(0, LEAVES_PER_MONTH - total_l)
    unmarked_count = len([d for d in wdays if d <= today and d.isoformat() not in marked])
    streak = get_streak(uid)
    user_rate, team_rate = attendance_rate(uid, year, month)

    rate_comparison = ""
    if user_rate >= team_rate:
        rate_comparison = f"  ✅ Above team avg ({team_rate}%)"
    else:
        rate_comparison = f"  · Team avg: {team_rate}%"

    send(uid,
        f"📊 <b>Your Attendance — {date(year, month, 1).strftime('%B %Y')}</b>\n\n"
        + "\n".join(lines) + "\n\n"
        f"🟢 <b>Present:</b> {total_p}   🟠 <b>Leave:</b> {total_l}   ⚪ <b>Unmarked:</b> {unmarked_count}\n"
        f"📈 <b>Attendance Rate:</b> {user_rate}%{rate_comparison}\n\n"
        f"{leave_bar(remain)}\n"
        f"Leaves remaining: <b>{remain}</b> / {LEAVES_PER_MONTH}"
        + streak_text(streak),
        reply_markup=persistent_menu(uid)
    )

def handle_whois(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid)); return

    text = msg.get("text", "").strip()
    query = text.split(" ", 1)[1].strip() if " " in text else ""
    if not query:
        send(uid, "Usage: /whois <i>name or username</i>", reply_markup=persistent_menu(uid)); return

    results = execute_query(
        "SELECT telegram_id, name, username FROM employees "
        "WHERE LOWER(name) LIKE %s OR LOWER(username) LIKE %s "
        "ORDER BY name LIMIT 5",
        (f"%{query.lower()}%", f"%{query.lower()}%"),
        fetch_all=True
    )
    if not results:
        send(uid, f"No employees matching '<b>{query}</b>'.", reply_markup=persistent_menu(uid)); return

    today = today_ist()
    lines = [f"🔍 <b>Results for '{query}'</b>\n"]
    for emp in results:
        streak = get_streak(emp["telegram_id"])
        today_s = already_marked(emp["telegram_id"], today)
        status_icon = {"present": "🟢", "leave": "🟠"}.get(today_s, "⚪")
        handle = f"@{emp['username']}" if emp["username"] else "—"
        streak_info = f"  🔥{streak}" if streak > 0 else ""
        lines.append(
            f"<b>{emp['name']}</b> ({handle})\n"
            f"   Today: {status_icon}{streak_info}   ID: <code>{emp['telegram_id']}</code>"
        )
    send(uid, "\n".join(lines), reply_markup=persistent_menu(uid))

def handle_remove(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid))
        return

    text = msg.get("text", "").strip()
    parts = text.split(" ", 1)
    
    if len(parts) < 2:
        send(uid, "⚠️ Usage: /remove <i>telegram_id</i>\n\nTip: Use /whois to find their ID.", reply_markup=persistent_menu(uid))
        return

    target_id_str = parts[1].strip()
    if not target_id_str.isdigit():
        send(uid, "❌ Please provide a valid numeric Telegram ID.", reply_markup=persistent_menu(uid))
        return
        
    target_id = int(target_id_str)
    
    emp = execute_query("SELECT name FROM employees WHERE telegram_id=%s", (target_id,), fetch_one=True)
    if not emp:
        send(uid, "❌ User not found in the database.", reply_markup=persistent_menu(uid))
        return
        
    # Archive them instead of deleting!
    execute_query("UPDATE employees SET is_active = FALSE, archived_at = NOW(), updated_at = NOW() WHERE telegram_id=%s", (target_id,), commit=True)
    
    send(uid, f"✅ Employee <b>{emp['name']}</b> has been archived.\n\nThey will no longer appear on the live dashboard or receive reminders, but their past attendance is saved for exports.", reply_markup=persistent_menu(uid))

def handle_archived(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid))
        return

    # Fetch all users where is_active is FALSE
    archived_emps = execute_query(
        "SELECT telegram_id, name, username FROM employees WHERE is_active = FALSE ORDER BY name", 
        fetch_all=True
    )

    if not archived_emps:
        send(uid, "📁 There are currently no archived employees.", reply_markup=persistent_menu(uid))
        return

    lines = ["📁 <b>Archived Employees</b>\n"]
    for emp in archived_emps:
        handle = f"@{emp['username']}" if emp["username"] else "—"
        lines.append(f"• <b>{emp['name']}</b> ({handle})\n   ID: <code>{emp['telegram_id']}</code>")

    send(uid, "\n".join(lines), reply_markup=persistent_menu(uid))

def handle_restore(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid))
        return

    text = msg.get("text", "").strip()
    parts = text.split(" ", 1)
    
    if len(parts) < 2:
        send(uid, "⚠️ Usage: /restore <i>telegram_id</i>\n\nTip: Use /archived to find their ID.", reply_markup=persistent_menu(uid))
        return

    target_id_str = parts[1].strip()
    if not target_id_str.isdigit():
        send(uid, "❌ Please provide a valid numeric Telegram ID.", reply_markup=persistent_menu(uid))
        return
        
    target_id = int(target_id_str)
    
    emp = execute_query("SELECT name, is_active FROM employees WHERE telegram_id=%s", (target_id,), fetch_one=True)
    if not emp:
        send(uid, "❌ User not found in the database.", reply_markup=persistent_menu(uid))
        return
        
    if emp["is_active"]:
        send(uid, f"ℹ️ Employee <b>{emp['name']}</b> is already active.", reply_markup=persistent_menu(uid))
        return

    execute_query("UPDATE employees SET is_active = TRUE, archived_at = NULL, updated_at = NOW() WHERE telegram_id=%s", (target_id,), commit=True)
    send(uid, f"✅ Employee <b>{emp['name']}</b> has been restored.\n\nThey will now appear on the active dashboard and receive reminders again.", reply_markup=persistent_menu(uid))

def handle_addholiday(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid))
        return

    text = msg.get("text", "").strip()
    args_str = text[len("/addholiday"):].strip()
    if not args_str:
        send(uid, "⚠️ Usage: /addholiday <i>YYYY-MM-DD</i> <i>[Description]</i>\n"
                  "Or range: /addholiday <i>YYYY-MM-DD to YYYY-MM-DD</i> <i>[Description]</i>\n\n"
                  "Examples:\n"
                  "• <code>/addholiday 2026-06-15 Eid al-Adha</code>\n"
                  "• <code>/addholiday 2026-10-20 to 2026-10-25 Puja Holidays</code>", reply_markup=persistent_menu(uid))
        return

    match_range = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(?:to|through|-)\s+(\d{4}-\d{2}-\d{2})(?:\s+(.*))?$", args_str, re.IGNORECASE)
    match_slash = re.match(r"^(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})(?:\s+(.*))?$", args_str)
    
    start_str = None
    end_str = None
    desc = "Holiday"
    
    if match_range:
        start_str, end_str, desc_group = match_range.groups()
        if desc_group: desc = desc_group.strip()
    elif match_slash:
        start_str, end_str, desc_group = match_slash.groups()
        if desc_group: desc = desc_group.strip()
    else:
        match_single = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(.*))?$", args_str)
        if match_single:
            start_str, desc_group = match_single.groups()
            if desc_group: desc = desc_group.strip()
        else:
            send(uid, "❌ Invalid format. Please use YYYY-MM-DD or YYYY-MM-DD to YYYY-MM-DD.", reply_markup=persistent_menu(uid))
            return

    try:
        start_d = date.fromisoformat(start_str)
    except ValueError:
        send(uid, "❌ Invalid start date format (must be YYYY-MM-DD).", reply_markup=persistent_menu(uid))
        return

    dates_to_add = [start_d]
    if end_str:
        try:
            end_d = date.fromisoformat(end_str)
        except ValueError:
            send(uid, "❌ Invalid end date format (must be YYYY-MM-DD).", reply_markup=persistent_menu(uid))
            return
        if end_d < start_d:
            send(uid, "❌ End date must be after or equal to start date.", reply_markup=persistent_menu(uid))
            return
        delta = end_d - start_d
        for i in range(1, delta.days + 1):
            dates_to_add.append(start_d + timedelta(days=i))

    try:
        for d in dates_to_add:
            execute_query(
                "INSERT INTO holidays (date, description) VALUES (%s, %s) "
                "ON CONFLICT (date) DO UPDATE SET description=EXCLUDED.description",
                (d.isoformat(), desc),
                commit=True
            )
        if len(dates_to_add) == 1:
            send(uid, f"✅ Holiday added:\n📅 <b>{start_d.strftime('%A, %d %B %Y')}</b>\n🎉 <i>{desc}</i>", reply_markup=persistent_menu(uid))
        else:
            send(uid, f"✅ Added range of {len(dates_to_add)} holidays:\n📅 <b>{start_d.strftime('%d %b %Y')}</b> to <b>{dates_to_add[-1].strftime('%d %b %Y')}</b>\n🎉 <i>{desc}</i>", reply_markup=persistent_menu(uid))
    except Exception as e:
        send(uid, f"❌ Database error: {str(e)}", reply_markup=persistent_menu(uid))

def handle_removeholiday(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid))
        return

    text = msg.get("text", "").strip()
    args_str = text[len("/removeholiday"):].strip()
    if not args_str:
        send(uid, "⚠️ Usage: /removeholiday <i>YYYY-MM-DD</i>\n"
                  "Or range: /removeholiday <i>YYYY-MM-DD to YYYY-MM-DD</i>\n\n"
                  "Examples:\n"
                  "• <code>/removeholiday 2026-06-15</code>\n"
                  "• <code>/removeholiday 2026-10-20 to 2026-10-25</code>", reply_markup=persistent_menu(uid))
        return

    match_range = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(?:to|through|-)\s+(\d{4}-\d{2}-\d{2})$", args_str, re.IGNORECASE)
    match_slash = re.match(r"^(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})$", args_str)
    
    start_str = None
    end_str = None
    
    if match_range:
        start_str, end_str = match_range.groups()
    elif match_slash:
        start_str, end_str = match_slash.groups()
    else:
        match_single = re.match(r"^(\d{4}-\d{2}-\d{2})$", args_str)
        if match_single:
            start_str = match_single.group(1)
        else:
            send(uid, "❌ Invalid format. Please use YYYY-MM-DD or YYYY-MM-DD to YYYY-MM-DD.", reply_markup=persistent_menu(uid))
            return

    try:
        start_d = date.fromisoformat(start_str)
    except ValueError:
        send(uid, "❌ Invalid start date format (must be YYYY-MM-DD).", reply_markup=persistent_menu(uid))
        return

    dates_to_remove = [start_d]
    if end_str:
        try:
            end_d = date.fromisoformat(end_str)
        except ValueError:
            send(uid, "❌ Invalid end date format (must be YYYY-MM-DD).", reply_markup=persistent_menu(uid))
            return
        if end_d < start_d:
            send(uid, "❌ End date must be after or equal to start date.", reply_markup=persistent_menu(uid))
            return
        delta = end_d - start_d
        for i in range(1, delta.days + 1):
            dates_to_remove.append(start_d + timedelta(days=i))

    try:
        placeholders = ", ".join(["%s"] * len(dates_to_remove))
        params = [d.isoformat() for d in dates_to_remove]
        existing = execute_query(f"SELECT COUNT(*) as count FROM holidays WHERE date IN ({placeholders})", tuple(params), fetch_one=True)
        count = existing["count"] if existing else 0
        
        if count == 0:
            if len(dates_to_remove) == 1:
                send(uid, f"❌ No holiday found on <b>{start_str}</b>.", reply_markup=persistent_menu(uid))
            else:
                send(uid, f"❌ No holidays found in range <b>{start_str}</b> to <b>{end_str}</b>.", reply_markup=persistent_menu(uid))
            return

        execute_query(f"DELETE FROM holidays WHERE date IN ({placeholders})", tuple(params), commit=True)
        
        if len(dates_to_remove) == 1:
            send(uid, f"✅ Holiday removed for 📅 <b>{start_d.strftime('%A, %d %B %Y')}</b>.", reply_markup=persistent_menu(uid))
        else:
            send(uid, f"✅ Removed {count} holidays in range 📅 <b>{start_d.strftime('%d %b %Y')}</b> to <b>{dates_to_remove[-1].strftime('%d %b %Y')}</b>.", reply_markup=persistent_menu(uid))
    except Exception as e:
        send(uid, f"❌ Database error: {str(e)}", reply_markup=persistent_menu(uid))

def handle_holidays(msg):
    uid = msg["from"]["id"]
    today = today_ist()
    
    # Show holidays for current year
    rows = execute_query(
        "SELECT date, description FROM holidays "
        "WHERE to_char(date, 'YYYY')=%s ORDER BY date ASC",
        (str(today.year),),
        fetch_all=True
    )
    
    if not rows:
        send(uid, f"📅 No holidays registered for the year <b>{today.year}</b>.", reply_markup=persistent_menu(uid))
        return

    lines = [f"📅 <b>Holidays for {today.year}</b>\n"]
    for r in rows:
        d = r["date"]
        d_obj = date.fromisoformat(d) if isinstance(d, str) else d
        past_label = " <i>(past)</i>" if d_obj < today else ""
        lines.append(f"• <code>{d_obj.strftime('%d %b %a')}</code>: <b>{r['description']}</b>{past_label}")

    send(uid, "\n".join(lines), reply_markup=persistent_menu(uid))

def handle_broadcast(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid)); return

    text = msg.get("text", "").strip()
    message = text.split(" ", 1)[1].strip() if " " in text else ""
    if not message:
        send(uid, "Usage: /broadcast <i>your message here</i>", reply_markup=persistent_menu(uid)); return

    employees = execute_query("SELECT telegram_id FROM employees WHERE is_active = TRUE", fetch_all=True)
    sent = 0
    for emp in employees:
        try:
            send(emp["telegram_id"],
                f"📢 <b>Announcement from Admin</b>\n\n{message}",
                reply_markup=persistent_menu(emp["telegram_id"])
            )
            sent += 1
        except Exception:
            pass
    send(uid, f"✅ Broadcast sent to <b>{sent}</b> / {len(employees)} employees.",
         reply_markup=persistent_menu(uid))

def handle_rename(msg):
    uid = msg["from"]["id"]
    text = msg.get("text", "").strip()
    new_name = text.split(" ", 1)[1].strip() if " " in text else ""
    if not new_name or len(new_name) < 2:
        send(uid, "Usage: /rename <i>Your New Name</i>\n\nName must be at least 2 characters.",
             reply_markup=persistent_menu(uid)); return

    old_name = get_user_name(uid)
    uname = msg["from"].get("username", "")
    register(uid, new_name, uname)
    send(uid,
        f"✅ Name updated!\n\n"
        f"<s>{old_name}</s> → <b>{new_name}</b>",
        reply_markup=persistent_menu(uid)
    )

def handle_admin_promote(msg):
    """Allow anyone to self-promote to admin using the shared password."""
    uid  = msg["from"]["id"]
    text = msg.get("text", "").strip()
    entered = text[len("/admin"):].strip()

    if is_admin(uid):
        send(uid,
            f"✅ <b>{get_user_name(uid)}</b>, you already have admin access!",
            reply_markup=persistent_menu(uid))
        return

    if not entered:
        send(uid,
            "🔐 <b>Admin Access</b>\n\n"
            "Type <code>/admin &lt;password&gt;</code> to unlock admin features.\n"
            "Contact the bot owner for the password.",
            reply_markup=persistent_menu(uid))
        return

    if entered == ADMIN_PASSWORD:
        ELEVATED_ADMINS.add(uid)
        name = get_user_name(uid)
        send(uid,
            f"✅ <b>Admin access granted, {name}!</b>\n\n"
            "You can now use:\n"
            "• 📋 Admin Report\n"
            "• 📥 Export CSV\n"
            "• /whois — look up employees\n"
            "• /broadcast — message everyone\n\n"
            "<i>Access lasts until the server restarts.</i>",
            reply_markup=persistent_menu(uid))
    else:
        send(uid,
            "❌ <b>Wrong password.</b>\n\nContact the bot owner for access.",
            reply_markup=persistent_menu(uid))

def handle_report(msg):
    uid  = msg["from"]["id"]
    text = msg.get("text", "").strip()
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid)); return

    cmd = next((c for c in ("/report", "Admin Report", "📋 Admin Report") if text.startswith(c)), "/report")
    year, month = parse_month_arg(text, cmd)
    if year is None:
        send(uid,
            "⚠️ Couldn't understand that month.\n\n"
            "<b>Examples:</b>\n"
            "• /report <i>(current month)</i>\n"
            "• /report last\n"
            "• /report May\n"
            "• /report May 2025\n"
            "• /report 2025-05",
            reply_markup=persistent_menu(uid)); return

    today      = today_ist()
    is_current = (year == today.year and month == today.month)
    wdays_all  = working_days_in_month(year, month)
    wdays_past = [d for d in wdays_all if d <= today] if is_current else wdays_all
    month_label = date(year, month, 1).strftime("%B %Y")

    # Includes active employees OR archived employees who had attendance this month
    employees = execute_query(
        "SELECT * FROM employees WHERE is_active = TRUE OR telegram_id IN "
        "(SELECT telegram_id FROM attendance WHERE to_char(date, 'YYYY-MM')=%s) "
        "ORDER BY name", 
        (f"{year:04d}-{month:02d}",), fetch_all=True
    )

    if not employees:
        send(uid, "No employees registered yet.", reply_markup=persistent_menu(uid)); return

    lines = [f"<b>Team Report — {month_label}</b>\n"]
    for emp in employees:
        rows = execute_query(
            "SELECT date, status FROM attendance WHERE telegram_id=%s "
            "AND to_char(date, 'YYYY-MM')=%s",
            (emp["telegram_id"], f"{year:04d}-{month:02d}"),
            fetch_all=True
        )
        marked   = {(r["date"].isoformat() if hasattr(r["date"], 'isoformat') else r["date"]): r["status"] for r in rows}
        present  = sum(1 for v in marked.values() if v == "present")
        on_leave = sum(1 for v in marked.values() if v == "leave")
        unmarked = len([d for d in wdays_past if d.isoformat() not in marked])
        remain   = max(0, LEAVES_PER_MONTH - on_leave)
        lines.append(
            f"<b>{emp['name']}</b>\n"
            f"   🟢 {present} P   🟠 {on_leave} L   ⚪ {unmarked} U   🍃 {remain} left"
        )

    today_note = ""
    if is_current:
        today_present = execute_query(
            "SELECT COUNT(*) AS n FROM attendance WHERE date=%s AND status='present'",
            (today.isoformat(),), fetch_one=True
        )["n"]
        today_leave = execute_query(
            "SELECT COUNT(*) AS n FROM attendance WHERE date=%s AND status='leave'",
            (today.isoformat(),), fetch_one=True
        )["n"]
        today_note = f"\n<b>Today ({today.strftime('%d %b')}):</b> {today_present} present · {today_leave} on leave · {len(employees)-today_present-today_leave} not yet marked\n"

    lines.append(today_note)
    lines.append(f"🌐 <b>Dashboard:</b> {WEBHOOK_URL}/dashboard")

    send(uid, "\n".join(lines), reply_markup=persistent_menu(uid))

def generate_and_send_csv(uid: int, year: int, month: int):
    """Build and send the attendance CSV for a given month."""
    today      = today_ist()
    days_in_month = monthrange(year, month)[1]
    all_weekdays = [date(year, month, d) for d in range(1, days_in_month + 1)
                    if not is_weekend(date(year, month, d))]
    month_label = date(year, month, 1).strftime("%B %Y")

    # Includes active employees OR archived employees who had attendance this month
    employees = execute_query(
        "SELECT * FROM employees WHERE is_active = TRUE OR telegram_id IN "
        "(SELECT telegram_id FROM attendance WHERE to_char(date, 'YYYY-MM')=%s) "
        "ORDER BY name", 
        (f"{year:04d}-{month:02d}",), fetch_all=True
    )
    all_att = execute_query(
        "SELECT telegram_id, date, status FROM attendance "
        "WHERE to_char(date, 'YYYY-MM')=%s",
        (f"{year:04d}-{month:02d}",),
        fetch_all=True
    )

    att_map = {}
    for r in all_att:
        d_key = r["date"].isoformat() if hasattr(r["date"], 'isoformat') else r["date"]
        att_map[(r["telegram_id"], d_key)] = r["status"]

    csv_lines = ["Name,Username," + ",".join(d.strftime("%d-%b") for d in all_weekdays) + ",Present,Leave,Unmarked,Leaves Remaining"]
    for emp in employees:
        row_data = []
        p = l = u = 0
        for d in all_weekdays:
            if is_holiday(d):
                row_data.append("Holiday")
            else:
                s = att_map.get((emp["telegram_id"], d.isoformat()), "")
                if s == "present":   row_data.append("P"); p += 1
                elif s == "leave":   row_data.append("L"); l += 1
                else:                row_data.append(""); u += 1
        csv_lines.append(
            f"{emp['name']},{emp['username'] or ''}," +
            ",".join(row_data) +
            f",{p},{l},{u},{max(0,LEAVES_PER_MONTH-l)}"
        )

    csv_text = "\n".join(csv_lines)
    fname    = f"attendance_{year}_{month:02d}.csv"

    with open(fname, "w", encoding="utf-8") as f:
        f.write(csv_text)

    with open(fname, "rb") as f:
        requests.post(
            f"{TG_API}/sendDocument",
            data={
                "chat_id": uid,
                "caption": f"📊 Attendance export — {month_label}",
                "reply_markup": json.dumps(persistent_menu(uid))
            },
            files={"document": f}
        )

    os.remove(fname)

def handle_export(msg):
    uid  = msg["from"]["id"]
    text = msg.get("text", "").strip()
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid)); return

    # If the admin typed a specific month (e.g. /export May 2025), go directly
    cmd = next((c for c in ("/export", "Export CSV", "📥 Export CSV") if text.startswith(c)), "/export")
    raw_arg = text[len(cmd):].strip()

    if raw_arg:  # they specified a month — try to parse it
        year, month = parse_month_arg(text, cmd)
        if year is None:
            send(uid,
                "⚠️ Couldn't understand that month.\n\n"
                "<b>Examples:</b>\n"
                "• /export <i>(shows month picker)</i>\n"
                "• /export last\n"
                "• /export May\n"
                "• /export May 2025\n"
                "• /export 2025-05",
                reply_markup=persistent_menu(uid)); return
        generate_and_send_csv(uid, year, month)
        return

    # No argument — show the month-picker inline keyboard
    today = today_ist()
    buttons = []
    for i in range(4):  # current + 3 previous months
        d = date(today.year, today.month, 1) - timedelta(days=1) * 0  # start from current
        # step back i months
        y, m = today.year, today.month
        for _ in range(i):
            first = date(y, m, 1)
            prev  = first - timedelta(days=1)
            y, m  = prev.year, prev.month
        label = date(y, m, 1).strftime("%B %Y")
        tag   = "(current)" if i == 0 else ""
        buttons.append([{"text": f"📅 {label} {tag}".strip(),
                         "callback_data": f"export:{y:04d}-{m:02d}"}])

    send(uid,
        "📥 <b>Select a month to export:</b>",
        reply_markup={"inline_keyboard": buttons}
    )

def handle_callback_query(cq):
    """Handle inline keyboard button taps."""
    cq_id  = cq["id"]
    uid    = cq["from"]["id"]
    data   = cq.get("data", "")

    # Always acknowledge the callback immediately (removes loading spinner)
    tg("answerCallbackQuery", callback_query_id=cq_id)

    if data.startswith("export:"):
        if not is_admin(uid):
            tg("answerCallbackQuery", callback_query_id=cq_id, text="Admin only.")
            return
        month_str = data[len("export:"):]  # e.g. "2026-05"
        try:
            y, m = map(int, month_str.split("-"))
        except ValueError:
            return
        month_label = date(y, m, 1).strftime("%B %Y")
        # Edit the picker message to confirm which month was chosen
        if "message" in cq:
            tg("editMessageText",
               chat_id=cq["message"]["chat"]["id"],
               message_id=cq["message"]["message_id"],
               text=f"📥 Generating export for <b>{month_label}</b>...",
               parse_mode="HTML")
        generate_and_send_csv(uid, y, m)

