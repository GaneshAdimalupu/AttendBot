# AttendBot — Frictionless Attendance & Leave System

A Telegram bot + live web dashboard that replaces messy WhatsApp group polls. Employees mark daily attendance with a single tap. Admins get real-time dashboards, CSV exports, team reports, and broadcast messaging — all inside Telegram.

---

## Features

| Category | Feature |
|---|---|
| **Employee UX** | Persistent reply keyboard — no commands needed, just tap |
| **Registration** | First-time users type their full name; button labels are never saved as names |
| **Attendance** | Mark Present or Take Leave once per day; switch status anytime |
| **Leave Tracking** | 4 leaves/month enforced; balance shown as a visual bar |
| **Streaks** | Consecutive present-day streaks with milestone celebrations at 5/10/15/20/25/50 days |
| **Attendance Rate** | Personal % vs. team average shown in Check Balance |
| **Weekend Awareness** | Saturdays & Sundays automatically excluded from all calculations |
| **Smart Greetings** | IST-aware "Good morning / afternoon / evening" responses |
| **Casual Replies** | Responds naturally to hi, hello, thanks, etc. |
| **Admin Report** | Instant team summary with per-employee P/L/U breakdown |
| **Export CSV** | Month-picker inline keyboard (current + 3 prior months); or `/export May 2025` |
| **Historical Reports** | `/report May 2025`, `/report last`, `/report 2025-05` |
| **Admin Lookup** | `/whois <name>` — fuzzy search with today's status and streak |
| **Broadcast** | `/broadcast <message>` — send announcements to all employees |
| **Self-service Rename** | `/rename New Name` — users update their own display name |
| **Username Sync** | Telegram @username updated silently on every interaction |
| **Live Dashboard** | Auto-refreshing web UI with KPIs, today's headcount, monthly calendar heatmap |
| **Timezone** | All operations pinned to IST (`Asia/Kolkata`) |
| **Database** | PostgreSQL with connection-per-query wrapper (no idle connections) |

---

## Quick Start for Evaluators

> You can test **all** features including admin ones without any setup.

1. Start the bot → `/start` → type your name when prompted
2. Unlock admin access:
   ```
   /admin attendbot123
   ```
3. You now have full admin access — try **📋 Admin Report**, **📥 Export CSV**, `/whois`, `/broadcast`

> The default password is `attendbot123`. It can be changed via the `ADMIN_PASSWORD` environment variable.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | From [@BotFather](https://t.me/botfather) |
| `DATABASE_URL` | ✅ | PostgreSQL connection string (e.g. from [Neon](https://neon.tech) or Render) |
| `WEBHOOK_URL` | ✅ | Your public server URL, no trailing slash |
| `ADMIN_IDS` | Optional | Comma-separated Telegram user IDs for permanent admins |
| `ADMIN_PASSWORD` | Optional | Password for `/admin` self-promotion (default: `attendbot123`) |
| `PORT` | Optional | Server port (default: `5000`) |

---

## Bot Commands

### Everyone
| Command | Description |
|---|---|
| `/start` or `/help` | Welcome message and command list |
| `/status` or `/leaves` | Your monthly attendance calendar + rate vs. team avg |
| `/rename New Name` | Update your display name |
| `/admin <password>` | Unlock admin features for this session |

### Keyboard Buttons
| Button | Action |
|---|---|
| ✅ Mark Present | Mark yourself present today |
| 🏖️ Take Leave | Mark a leave day (enforces monthly limit) |
| 📊 Check Balance | Full monthly stats with attendance rate |

### Admin Only
| Command | Description |
|---|---|
| 📋 Admin Report | Team summary (works with month arg: `Admin Report May 2025`) |
| 📥 Export CSV | Shows month picker (current + 3 prior); or `/export May 2025` |
| `/report [month]` | Team report — supports `last`, `May`, `May 2025`, `2025-05` |
| `/export [month]` | CSV export — same month formats as `/report` |
| `/whois <name>` | Look up employee by name/username fragment |
| `/broadcast <msg>` | Send an announcement to all registered employees |

---

## Local Development

### Prerequisites
- Python 3.9+
- A PostgreSQL database (free options: [Neon.tech](https://neon.tech), [Supabase](https://supabase.com))
- [ngrok](https://ngrok.com/) for a public tunnel

### Setup

1. **Clone and install:**
   ```bash
   git clone https://github.com/GaneshAdimalupu/AttendBot.git
   cd AttendBot/attendance_system
   pip install -r requirements.txt
   ```

2. **Create `.env`:**
   ```env
   BOT_TOKEN=your_telegram_bot_token
   DATABASE_URL=postgresql://user:password@host/dbname
   ADMIN_IDS=your_telegram_user_id
   WEBHOOK_URL=https://xxxx.ngrok-free.app
   ADMIN_PASSWORD=attendbot123
   ```

3. **Start ngrok:**
   ```bash
   ngrok http 5000
   ```
   Copy the `https://...ngrok-free.app` URL into `WEBHOOK_URL` in `.env`.

4. **Run the server:**
   ```bash
   python run.py
   ```

5. **Register webhook + commands:**
   Visit `http://localhost:5000/setup` in your browser.
   This sets the webhook, registers the `/` command menu, and sets the bot description in one call.

6. **Seed demo data (optional):**
   Visit `http://localhost:5000/demo/seed` to populate 10 fake employees with realistic attendance history.

7. **View dashboard:**
   Open `http://localhost:5000/dashboard`

---

## Deploying to Render

1. Push your code to GitHub. Make sure `.env` is in `.gitignore`.

2. Go to [Render.com](https://render.com) → **New Web Service** → connect your repo.

3. Configure:
   | Setting | Value |
   |---|---|
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn bot:app --bind 0.0.0.0:$PORT --workers 1` |

4. Add Environment Variables:
   - `BOT_TOKEN`
   - `DATABASE_URL` ← use the **external** connection string from your DB provider
   - `WEBHOOK_URL` ← your Render URL, e.g. `https://attendbot.onrender.com`
   - `ADMIN_IDS`
   - `ADMIN_PASSWORD`

5. Deploy → once live, visit `https://your-app.onrender.com/setup` to register the webhook.

### Daily Reminders (Optional Cron Job)

Set up an external cron service (e.g. [cron-job.org](https://cron-job.org)) to hit this URL on weekday mornings:

```
GET https://your-app.onrender.com/cron/remind
```

Employees who haven't marked attendance yet get a smart reminder (morning/afternoon/evening greeting based on IST time). Weekends are automatically skipped.

---

## Project Structure

```
attendance_system/
├── bot.py            # All bot logic, handlers, dashboard HTML, API routes
├── run.py            # Local dev entry point (loads .env automatically)
├── requirements.txt  # Python dependencies
├── Procfile          # Render/Heroku process definition
├── .env              # Local secrets (never committed)
└── .gitignore        # Excludes .env, __pycache__, etc.
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.9+ |
| Web Framework | Flask |
| Bot API | Telegram Bot API (webhooks) |
| Database | PostgreSQL via `psycopg2` |
| Dashboard | Vanilla HTML/CSS/JS (embedded in `bot.py`) |
| Hosting | Render.com |
| Timezone | `zoneinfo` (stdlib) — Asia/Kolkata |
| Local Dev | `python-dotenv` |

---

## Database Schema

```sql
CREATE TABLE employees (
    telegram_id   BIGINT PRIMARY KEY,
    name          TEXT NOT NULL,
    username      TEXT,
    registered_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE attendance (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    date        DATE NOT NULL,
    status      TEXT NOT NULL,        -- 'present' | 'leave'
    marked_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE(telegram_id, date)
);
```

Tables are created automatically on first run via `init_db()`.