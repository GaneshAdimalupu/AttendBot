"""
TinkerHub Attendance Bot
========================
A Telegram bot for frictionless daily attendance marking.
Upgraded with a Persistent Reply Keyboard for zero-friction UX.
Admins get full visibility via the web dashboard.
"""

import os, sqlite3, json
from datetime import date, datetime, timedelta
from calendar import monthrange
from flask import Flask, request, jsonify, render_template_string
import requests

# ── Configuration ────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS   = set(map(int, os.environ.get("ADMIN_IDS", "0").split(",")))  # Telegram user IDs
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # e.g. https://yourapp.onrender.com
LEAVES_PER_MONTH = 4
DB_PATH     = "attendance.db"

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# ── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            telegram_id   INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            username      TEXT,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            date        TEXT NOT NULL,          -- YYYY-MM-DD
            status      TEXT NOT NULL,          -- present | leave
            marked_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_id, date)
        );
        """)

# ── Telegram helpers ──────────────────────────────────────────────────────────
def tg(method, **kwargs):
    resp = requests.post(f"{TG_API}/{method}", json=kwargs, timeout=10)
    return resp.json()

def send(chat_id, text, **kwargs):
    return tg("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", **kwargs)

# ── Business logic ────────────────────────────────────────────────────────────
def is_weekend(d: date) -> bool:
    return d.weekday() >= 5   # Saturday=5, Sunday=6

def working_days_in_month(year: int, month: int):
    days_in_month = monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, days_in_month + 1)
            if not is_weekend(date(year, month, d))]

def leave_count(telegram_id: int, year: int, month: int) -> int:
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) AS n FROM attendance "
            "WHERE telegram_id=? AND status='leave' "
            "AND strftime('%Y-%m', date)=?",
            (telegram_id, f"{year:04d}-{month:02d}")
        ).fetchone()
    return row["n"]

def already_marked(telegram_id: int, d: date) -> str | None:
    with get_db() as db:
        row = db.execute(
            "SELECT status FROM attendance WHERE telegram_id=? AND date=?",
            (telegram_id, d.isoformat())
        ).fetchone()
    return row["status"] if row else None

def mark(telegram_id: int, d: date, status: str):
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO attendance(telegram_id, date, status) VALUES (?,?,?)",
            (telegram_id, d.isoformat(), status)
        )

def register(telegram_id: int, name: str, username: str):
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO employees(telegram_id, name, username) VALUES (?,?,?)",
            (telegram_id, name, username or "")
        )

def is_registered(telegram_id: int) -> bool:
    with get_db() as db:
        row = db.execute("SELECT 1 FROM employees WHERE telegram_id=?", (telegram_id,)).fetchone()
    return row is not None

def get_user_name(telegram_id: int) -> str:
    with get_db() as db:
        row = db.execute("SELECT name FROM employees WHERE telegram_id=?", (telegram_id,)).fetchone()
    return row["name"] if row else "Employee"

def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS

def get_streak(telegram_id: int) -> int:
    today = date.today()
    streak = 0
    d = today
    while True:
        if is_weekend(d):
            d -= timedelta(days=1)
            continue
        with get_db() as db:
            row = db.execute(
                "SELECT status FROM attendance WHERE telegram_id=? AND date=?",
                (telegram_id, d.isoformat())
            ).fetchone()
        if row and row["status"] == "present":
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak

def is_late_mark() -> bool:
    now = datetime.now()
    return now.hour >= 11

# ── Message/button builders ───────────────────────────────────────────────────
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

def streak_text(streak: int) -> str:
    if streak == 0:
        return ""
    if streak >= 10:
        return f"\n\n🔥 <b>{streak}-day streak!</b> Incredible dedication!"
    if streak >= 5:
        return f"\n\n🔥 <b>{streak}-day streak!</b> Keep it going!"
    return f"\n\n🔥 Streak: {streak} days"

def leave_bar(remaining: int) -> str:
    used = LEAVES_PER_MONTH - remaining
    return "🟩" * remaining + "⬜" * used

# ── Command / callback handlers ───────────────────────────────────────────────
def handle_start(msg):
    uid = msg["from"]["id"]
    name = get_user_name(uid)

    send(uid,
        f"Hi <b>{name}</b>! Welcome back to <b>AttendBot</b>.\n\n"
        "Use the menu below — it only takes <b>one tap</b> to mark attendance!\n\n"
        "• <b>Mark Present</b> — mark yourself present\n"
        "• <b>Take Leave</b> — mark a leave day\n"
        "• <b>Check Balance</b> — view your monthly stats\n\n"
        "Just tap below:",
        reply_markup=persistent_menu(uid)
    )

def handle_direct_mark(msg, status: str):
    uid = msg["from"]["id"]
    today = date.today()
    
    if is_weekend(today):
        send(uid, "It's a weekend — no attendance needed.\nEnjoy your break! See you on Monday.",
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
    today  = date.today()
    year, month = today.year, today.month
    wdays  = working_days_in_month(year, month)

    with get_db() as db:
        rows = db.execute(
            "SELECT date, status FROM attendance WHERE telegram_id=? "
            "AND strftime('%Y-%m', date)=? ORDER BY date",
            (uid, f"{year:04d}-{month:02d}")
        ).fetchall()

    marked = {r["date"]: r["status"] for r in rows}
    lines  = []
    for d in wdays:
        ds = d.isoformat()
        if d > today:
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

    send(uid,
        f"📊 <b>Your Attendance — {date(year, month, 1).strftime('%B %Y')}</b>\n\n"
        + "\n".join(lines) + "\n\n"
        f"🟢 <b>Present:</b> {total_p}   🟠 <b>Leave:</b> {total_l}   ⚪ <b>Unmarked:</b> {unmarked_count}\n\n"
        f"{leave_bar(remain)}\n"
        f"Leaves remaining: <b>{remain}</b> / {LEAVES_PER_MONTH}"
        + streak_text(streak),
        reply_markup=persistent_menu(uid)
    )

def handle_report(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid)); return

    today = date.today()
    year, month = today.year, today.month
    wdays_past = [d for d in working_days_in_month(year, month) if d <= today]

    with get_db() as db:
        employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()

    if not employees:
        send(uid, "No employees registered yet.", reply_markup=persistent_menu(uid)); return

    lines = [f"<b>Team Report — {date(year,month,1).strftime('%B %Y')}</b> ({today.strftime('%d %b')})\n"]
    for emp in employees:
        with get_db() as db:
            rows = db.execute(
                "SELECT date, status FROM attendance WHERE telegram_id=? "
                "AND strftime('%Y-%m', date)=?",
                (emp["telegram_id"], f"{year:04d}-{month:02d}")
            ).fetchall()
        marked   = {r["date"]: r["status"] for r in rows}
        present  = sum(1 for v in marked.values() if v == "present")
        on_leave = sum(1 for v in marked.values() if v == "leave")
        unmarked = len([d for d in wdays_past if d.isoformat() not in marked])
        remain   = max(0, LEAVES_PER_MONTH - on_leave)
        lines.append(
            f"<b>{emp['name']}</b>\n"
            f"   🟢 {present} P   🟠 {on_leave} L   ⚪ {unmarked} U   🍃 {remain} left"
        )

    with get_db() as db:
        today_present = db.execute(
            "SELECT COUNT(*) AS n FROM attendance WHERE date=? AND status='present'",
            (today.isoformat(),)
        ).fetchone()["n"]
        today_leave = db.execute(
            "SELECT COUNT(*) AS n FROM attendance WHERE date=? AND status='leave'",
            (today.isoformat(),)
        ).fetchone()["n"]

    lines.append(f"\n<b>Today:</b> {today_present} present · {today_leave} on leave · {len(employees)-today_present-today_leave} not yet marked\n")
    lines.append(f"🌐 <b>Dashboard:</b> {WEBHOOK_URL}/dashboard")

    send(uid, "\n".join(lines), reply_markup=persistent_menu(uid))

def handle_export(msg):
    uid = msg["from"]["id"]
    if not is_admin(uid):
        send(uid, "Admin only.", reply_markup=persistent_menu(uid)); return

    today = date.today()
    year, month = today.year, today.month
    wdays = working_days_in_month(year, month)

    with get_db() as db:
        employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()
        all_att   = db.execute(
            "SELECT telegram_id, date, status FROM attendance "
            "WHERE strftime('%Y-%m', date)=?",
            (f"{year:04d}-{month:02d}",)
        ).fetchall()

    att_map = {}
    for r in all_att:
        att_map[(r["telegram_id"], r["date"])] = r["status"]

    csv_lines = ["Name,Username," + ",".join(d.strftime("%d-%b") for d in wdays) + ",Present,Leave,Unmarked,Leaves Remaining"]
    for emp in employees:
        row_data = []
        p = l = u = 0
        for d in wdays:
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
                "caption": f"📊 Attendance export for {date(year,month,1).strftime('%B %Y')}",
                "reply_markup": json.dumps(persistent_menu(uid))
            },
            files={"document": f}
        )

    os.remove(fname)

# ── Webhook endpoint ──────────────────────────────────────────────────────────
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.json
    try:
        if "message" in update:
            msg  = update["message"]
            text = msg.get("text","").strip()
            uid  = msg["from"]["id"]

            # --- 1. Registration Flow Gatekeeper ---
            if not is_registered(uid):
                if text == "/start":
                    send(uid, "👋 Welcome to <b>AttendBot</b>!\n\nBefore we begin, please type your <b>Full Legal Name</b> as it should appear on official records:")
                else:
                    # Treat whatever they typed as their legal name
                    uname = msg["from"].get("username", "")
                    register(uid, text, uname)
                    send(uid, f"✅ Thank you, <b>{text}</b>! Your profile is set up.\n\nPlease use the menu below to update your status.", reply_markup=persistent_menu(uid))
                return jsonify(ok=True)

            # --- 2. Button Router (Only for Registered Users) ---
            if text in ["/start", "/help"]:
                handle_start(msg)
            elif text in ["✅ Mark Present", "Mark Present"]:
                handle_direct_mark(msg, "present")
            elif text in ["🏖️ Take Leave", "Take Leave"]:
                handle_direct_mark(msg, "leave")
            elif text in ["📊 Check Balance", "Check Balance", "/status", "/leaves"]:
                handle_status(msg)
            elif text in ["📋 Admin Report", "Admin Report", "/report"]:
                handle_report(msg)
            elif text in ["📥 Export CSV", "Export CSV", "/export"]:
                handle_export(msg)
            else:
                handle_start(msg)

    except Exception as e:
        print(f"Error: {e}")
    return jsonify(ok=True)

# ── Daily Reminder Endpoint ──────────────────────────────────────────────────
@app.route("/cron/remind")
def cron_remind():
    today = date.today()
    if is_weekend(today):
        return jsonify({"skipped": "weekend"})

    with get_db() as db:
        employees = db.execute("SELECT telegram_id, name FROM employees").fetchall()
        marked_today = set(
            r["telegram_id"] for r in db.execute(
                "SELECT telegram_id FROM attendance WHERE date=?",
                (today.isoformat(),)
            ).fetchall()
        )

    reminded = 0
    for emp in employees:
        if emp["telegram_id"] not in marked_today:
            send(emp["telegram_id"],
                f"Good morning, <b>{emp['name']}</b>!\n\n"
                f"<b>{today.strftime('%A, %d %B %Y')}</b>\n\n"
                "Don't forget to mark your attendance — just tap a button below:",
                reply_markup=persistent_menu(emp["telegram_id"])
            )
            reminded += 1

    return jsonify({"reminded": reminded, "total": len(employees), "already_marked": len(marked_today)})

# ── Admin web dashboard ───────────────────────────────────────────────────────
# ... (Dashboard HTML stays exactly the same) ...
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AttendBot — Admin Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0d0f14;
  --surface: #151820;
  --border: #1e2330;
  --accent: #4ade80;
  --accent2: #64748b;
  --danger: #f87171;
  --text: #e2e8f0;
  --muted: #64748b;
  --present: #4ade80;
  --leave: #64748b;
  --unmarked: #1e2330;
  --radius: 12px;
  --glass: rgba(21,24,32,.7);
}
* { box-sizing:border-box; margin:0; padding:0 }
body { background:var(--bg); color:var(--text); font-family:'Sora',sans-serif; min-height:100vh; }

@keyframes fadeUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
@keyframes countUp { from { opacity:0; transform:scale(.8); } to { opacity:1; transform:scale(1); } }
.fade-in { animation: fadeUp .5s ease both; }
.fade-d1 { animation-delay:.1s } .fade-d2 { animation-delay:.2s }
.fade-d3 { animation-delay:.3s } .fade-d4 { animation-delay:.4s }

header {
  padding:20px 32px;
  display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;
  border-bottom:1px solid var(--border);
  background:var(--surface);
  backdrop-filter:blur(12px);
}
.logo { display:flex; align-items:center; gap:10px; }
.logo-icon { width:36px; height:36px; background:var(--border); border-radius:8px;
  display:flex; align-items:center; justify-content:center; font-size:18px; }
h1 { font-size:1.1rem; font-weight:600; letter-spacing:.02em; }
.subtitle { font-size:.75rem; color:var(--muted); }
.header-right { display:flex; align-items:center; gap:12px; }
.month-badge { background:var(--border); padding:6px 14px; border-radius:20px;
  font-family:'DM Mono',monospace; font-size:.8rem; color:var(--text); }
.live-dot { width:8px; height:8px; background:var(--accent); border-radius:50%; animation:pulse 2s infinite; display:inline-block; }

main { max-width:1200px; margin:0 auto; padding:32px 24px; }

.search-wrap { margin-bottom:24px; }
.search-input { width:100%; max-width:360px; padding:10px 16px 10px 40px; border-radius:8px;
  border:1px solid var(--border); background:var(--surface); color:var(--text);
  font-family:'Sora',sans-serif; font-size:.85rem; outline:none; transition:border .2s; }
.search-input:focus { border-color:var(--accent); }
.search-wrap { position:relative; }
.search-wrap::before { content:'🔍'; position:absolute; left:14px; top:50%; transform:translateY(-50%); font-size:.8rem; }

.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin-bottom:32px; }
.kpi { background:var(--glass); backdrop-filter:blur(10px); border:1px solid var(--border);
  border-radius:var(--radius); padding:20px; position:relative; overflow:hidden;
  transition:transform .2s, box-shadow .2s; }
.kpi:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,0,0,.3); }
.kpi::before { content:''; position:absolute; top:0; left:0; right:0; height:3px;
  background:linear-gradient(90deg,var(--accent-color,var(--accent)),transparent); }
.kpi-val { font-size:2.2rem; font-weight:700; font-family:'DM Mono',monospace;
  color:var(--accent-color,var(--accent)); line-height:1; animation:countUp .6s ease both; }
.kpi-label { font-size:.72rem; color:var(--muted); margin-top:6px; text-transform:uppercase; letter-spacing:.08em; }

section { margin-bottom:36px; }
h2 { font-size:.85rem; font-weight:600; text-transform:uppercase; letter-spacing:.12em;
  color:var(--muted); margin-bottom:16px; padding-bottom:8px; border-bottom:1px solid var(--border); }

.team-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; }
.emp-card { background:var(--glass); backdrop-filter:blur(10px); border:1px solid var(--border);
  border-radius:var(--radius); padding:18px; transition:transform .2s, box-shadow .2s, border-color .2s; }
.emp-card:hover { transform:translateY(-3px); box-shadow:0 12px 32px rgba(0,0,0,.25); border-color:var(--accent)33; }
.emp-top { display:flex; align-items:center; gap:12px; margin-bottom:14px; }
.avatar { width:40px; height:40px; border-radius:50%; display:flex; align-items:center;
  justify-content:center; font-size:1rem; font-weight:700; flex-shrink:0; transition:transform .2s; }
.emp-card:hover .avatar { transform:scale(1.1); }
.emp-name { font-weight:600; font-size:.95rem; }
.emp-handle { font-size:.75rem; color:var(--muted); }
.stat-row { display:flex; gap:8px; margin-bottom:10px; }
.stat { flex:1; background:var(--bg); border-radius:6px; padding:8px; text-align:center; }
.stat-val { font-size:1.2rem; font-weight:700; font-family:'DM Mono',monospace; }
.stat-key { font-size:.65rem; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; margin-top:2px; }
.s-p { color:var(--present); } .s-l { color:var(--leave); }
.s-u { color:var(--muted); } .s-r { color:var(--muted); }

.leave-bar { height:6px; background:var(--bg); border-radius:3px; overflow:hidden; }
.leave-fill { height:100%; background:var(--present); border-radius:3px; transition:width .8s ease; }
.leave-meta { display:flex; justify-content:space-between; font-size:.7rem; color:var(--muted); margin-top:4px; }

.cal-strip { display:flex; flex-wrap:wrap; gap:4px; margin-top:10px; }
.cal-day { width:26px; height:26px; border-radius:5px; display:flex; align-items:center;
  justify-content:center; font-size:.6rem; font-family:'DM Mono',monospace; font-weight:500;
  transition:transform .15s; cursor:default; position:relative; }
.cal-day:hover { transform:scale(1.3); z-index:2; }
.cal-day[data-tip]:hover::after { content:attr(data-tip); position:absolute; bottom:110%; left:50%;
  transform:translateX(-50%); background:#1e2330; color:var(--text); padding:3px 8px;
  border-radius:4px; font-size:.6rem; white-space:nowrap; z-index:10; pointer-events:none; }
.cd-p { background:rgba(74,222,128,.2); color:var(--present); }
.cd-l { background:rgba(245,158,11,.2); color:var(--leave); }
.cd-u { background:var(--unmarked); color:var(--muted); }
.cd-w { background:transparent; color:#1e2330; }
.cd-f { background:var(--border); color:var(--border); }

.today-table { width:100%; border-collapse:collapse; font-size:.875rem; }
.today-table th { text-align:left; padding:10px 14px; background:var(--border);
  font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
.today-table td { padding:10px 14px; border-bottom:1px solid var(--border); }
.today-table tr:last-child td { border:none; }
.today-table tr { transition:background .15s; }
.today-table tbody tr:hover { background:rgba(74,222,128,.04); }
.badge { display:inline-flex; align-items:center; gap:5px; padding:3px 10px;
  border-radius:20px; font-size:.75rem; font-weight:600; }
.b-present { background:rgba(74,222,128,.15); color:var(--present); }
.b-leave   { background:rgba(245,158,11,.15);  color:var(--leave); }
.b-unmarked{ background:rgba(51,65,85,.4);     color:var(--muted); }

.refresh { font-size:.75rem; color:var(--muted); }
.refresh a { color:var(--accent); text-decoration:none; }
.refresh a:hover { text-decoration:underline; }

@media(max-width:600px){ main{padding:16px 12px} .kpi-val{font-size:1.8rem} .header-right{flex-wrap:wrap} }
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon">📋</div>
    <div>
      <h1>AttendBot</h1>
      <div class="subtitle">Attendance &amp; Leave Dashboard</div>
    </div>
  </div>
  <div class="header-right">
    <span class="month-badge" id="monthBadge"></span>
    <span class="refresh"><span class="live-dot"></span> Live · <a href="javascript:location.reload()">Refresh</a></span>
  </div>
</header>
<main>
  <div class="kpi-grid fade-in" id="kpis"></div>
  <section class="fade-in fade-d1">
    <h2>Today's Headcount</h2>
    <table class="today-table" id="todayTable">
      <thead><tr><th>Employee</th><th>Status</th><th>Marked at</th></tr></thead>
      <tbody id="todayBody"></tbody>
    </table>
  </section>
  <section class="fade-in fade-d2">
    <h2>Monthly Overview</h2>
    <div class="search-wrap"><input type="text" class="search-input" id="searchInput" placeholder="Search employees..."></div>
    <div class="team-grid" id="teamGrid"></div>
  </section>
</main>
<script>
const COLORS = ['#64748b'];

function animateCount(el, target) {
  let start = 0; const dur = 600; const t0 = performance.now();
  function step(now) {
    const p = Math.min((now - t0) / dur, 1);
    el.textContent = Math.round(p * target);
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

let allData = null;

async function load(){
  const data = await fetch('/api/dashboard').then(r=>r.json());
  allData = data;
  const today = new Date().toISOString().slice(0,10);
  const [year,month] = today.split('-').map(Number);
  const daysInMonth = new Date(year, month, 0).getDate();

  document.getElementById('monthBadge').textContent =
    new Date(year,month-1,1).toLocaleString('default',{month:'long',year:'numeric'});

  const t = data.today;
  const total = data.employees.length;
  const rate = total > 0 ? Math.round((t.present / total) * 100) : 0;
  const kpiData = [
    {val: total, label:'Total Employees', color:'#64748b'},
    {val: t.present,  label:'Present Today',  color:'#4ade80'},
    {val: t.on_leave, label:'On Leave Today',  color:'#64748b'},
    {val: t.unmarked, label:'Not Marked Yet',  color:'#64748b'},
    {val: rate, label:'Attendance Rate', color:'#4ade80', suffix:'%'},
  ];
  document.getElementById('kpis').innerHTML = kpiData.map((k,i)=>`
    <div class="kpi fade-in fade-d${i+1}" style="--accent-color:${k.color}">
      <div class="kpi-val" data-count="${k.val}">${k.val}${k.suffix||''}</div>
      <div class="kpi-label">${k.label}</div>
    </div>`).join('');

  document.querySelectorAll('.kpi-val[data-count]').forEach(el => {
    const target = parseInt(el.dataset.count);
    const suffix = el.textContent.includes('%') ? '%' : '';
    el.textContent = '0';
    animateCount(el, target);
    if(suffix) setTimeout(()=> el.textContent = target + suffix, 650);
  });

  document.getElementById('todayBody').innerHTML = data.employees.map((e,i)=>{
    const att = e.today_status;
    const badgeCls = att==='present'?'b-present':att==='leave'?'b-leave':'b-unmarked';
    const badgeTxt = att==='present'?'Present':att==='leave'?'On Leave':'Not Marked';
    const time = e.today_time ? new Date(e.today_time).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'}) : '—';
    return `<tr>
      <td style="display:flex;align-items:center;gap:10px;">
        <div class="avatar" style="background:${COLORS[i%COLORS.length]}22;color:${COLORS[i%COLORS.length]}">${e.name[0]}</div>
        <div><div style="font-weight:600">${e.name}</div><div style="font-size:.75rem;color:#64748b">@${e.username||'—'}</div></div>
      </td>
      <td><span class="badge ${badgeCls}">${badgeTxt}</span></td>
      <td style="color:#64748b;font-family:'DM Mono',monospace;font-size:.8rem">${time}</td>
    </tr>`;
  }).join('');

  renderCards(data.employees, year, month, daysInMonth, today);
  setTimeout(load, 60000);
}

function renderCards(employees, year, month, daysInMonth, today, filter='') {
  const filtered = filter ? employees.filter(e => e.name.toLowerCase().includes(filter) || (e.username||'').toLowerCase().includes(filter)) : employees;

  document.getElementById('teamGrid').innerHTML = filtered.map((e,i)=>{
    const {present,leave,unmarked,leaves_remaining} = e.month;
    const leaveUsed = 4 - leaves_remaining;
    const fillPct   = Math.round((leaves_remaining/4)*100);

    const calDays = [];
    for(let d=1;d<=daysInMonth;d++){
      const ds = `${year}-${String(month).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const dow = new Date(ds).getDay();
      const isFuture = ds > today;
      if(dow===0||dow===6){ calDays.push(`<div class="cal-day cd-w">${d}</div>`); continue; }
      const s = e.month.daily[ds];
      const cls = isFuture?'cd-f':s==='present'?'cd-p':s==='leave'?'cd-l':'cd-u';
      const tip = isFuture?'Upcoming':s==='present'?'Present':s==='leave'?'On Leave':'Not Marked';
      calDays.push(`<div class="cal-day ${cls}" data-tip="${ds}: ${tip}">${d}</div>`);
    }

    return `<div class="emp-card fade-in" style="animation-delay:${i*0.05}s">
      <div class="emp-top">
        <div class="avatar" style="background:${COLORS[i%COLORS.length]}22;color:${COLORS[i%COLORS.length]};font-size:1.1rem">${e.name[0]}</div>
        <div><div class="emp-name">${e.name}</div><div class="emp-handle">@${e.username||'—'}</div></div>
      </div>
      <div class="stat-row">
        <div class="stat"><div class="stat-val s-p">${present}</div><div class="stat-key">Present</div></div>
        <div class="stat"><div class="stat-val s-l">${leave}</div><div class="stat-key">Leave</div></div>
        <div class="stat"><div class="stat-val s-u">${unmarked}</div><div class="stat-key">Unmarked</div></div>
        <div class="stat"><div class="stat-val s-r">${leaves_remaining}</div><div class="stat-key">Left</div></div>
      </div>
      <div class="leave-bar"><div class="leave-fill" style="width:${fillPct}%"></div></div>
      <div class="leave-meta"><span>Leaves: ${leaves_remaining} remaining</span><span>${leaveUsed}/4 used</span></div>
      <div class="cal-strip">${calDays.join('')}</div>
    </div>`;
  }).join('');

  if(filtered.length === 0) {
    document.getElementById('teamGrid').innerHTML = '<div style="color:var(--muted);padding:24px;text-align:center">No employees match your search.</div>';
  }
}

document.getElementById('searchInput').addEventListener('input', function() {
  if(!allData) return;
  const today = new Date().toISOString().slice(0,10);
  const [year,month] = today.split('-').map(Number);
  const daysInMonth = new Date(year, month, 0).getDate();
  renderCards(allData.employees, year, month, daysInMonth, today, this.value.toLowerCase().trim());
});

load();
</script>
</body>
</html>"""

@app.route("/dashboard")
def dashboard():
    return DASHBOARD_HTML

@app.route("/api/dashboard")
def api_dashboard():
    today = date.today()
    year, month = today.year, today.month
    wdays_past = [d for d in working_days_in_month(year, month) if d <= today]

    with get_db() as db:
        employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()
        month_str = f"{year:04d}-{month:02d}"
        all_att   = db.execute(
            "SELECT telegram_id, date, status, marked_at FROM attendance "
            "WHERE strftime('%Y-%m', date)=?", (month_str,)
        ).fetchall()

    att_map = {}
    for r in all_att:
        att_map[(r["telegram_id"], r["date"])] = {"status": r["status"], "marked_at": r["marked_at"]}

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

    return jsonify({
        "employees": emp_data,
        "today": {"present": today_present, "on_leave": today_leave, "unmarked": today_unmarked}
    })

@app.route("/")
def index():
    return jsonify({"status": "ok", "bot": "AttendBot", "dashboard": "/dashboard"})

@app.route("/setup")
def setup():
    if WEBHOOK_URL:
        r = requests.post(f"{TG_API}/setWebhook",
                          json={"url": f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"})
        return jsonify(r.json())
    return jsonify({"error": "WEBHOOK_URL not set"})

@app.route("/demo/seed")
def seed_demo():
    import random
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
    today = date.today()
    year, month = today.year, today.month
    wdays = [d for d in working_days_in_month(year, month) if d <= today]

    with get_db() as db:
        for tid, name, uname in demo_employees:
            db.execute("INSERT OR IGNORE INTO employees(telegram_id,name,username) VALUES(?,?,?)",
                       (tid, name, uname))
        for d in wdays:
            for tid, _, _ in demo_employees:
                if random.random() < 0.05: continue 
                status = "leave" if random.random() < 0.12 else "present"
                db.execute("INSERT OR REPLACE INTO attendance(telegram_id,date,status) VALUES(?,?,?)",
                           (tid, d.isoformat(), status))

    return jsonify({"seeded": len(demo_employees), "days": len(wdays)})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)