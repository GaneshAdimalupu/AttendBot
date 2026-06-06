# AttendBot — Attendance & Leave Management System

A Telegram bot + web dashboard that replaces the WhatsApp poll system.

## Quick Start (Local)

```bash
pip install -r requirements.txt

# Set your bot token (from @BotFather) and your Telegram user ID
BOT_TOKEN=your_token ADMIN_IDS=your_telegram_id python run.py

# Seed demo data
curl http://localhost:5000/demo/seed

# View dashboard
open http://localhost:5000/dashboard
```

## Deploy to Render (Free)

1. Push this folder to a GitHub repo
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set environment variables:
   - `BOT_TOKEN` — from @BotFather
   - `ADMIN_IDS` — your Telegram numeric user ID (get it from @userinfobot)
   - `WEBHOOK_URL` — your Render app URL e.g. `https://attendbot.onrender.com`
4. After deploy, visit `https://yourapp.onrender.com/setup` once to register the webhook
5. Share your bot username with employees — they just send /start

## Employee Commands

| Command | Action |
|---------|--------|
| `/mark` | Mark today's attendance (or just send any message) |
| `/status` | Full month view with calendar |
| `/leaves` | Quick leave balance |
| `/help` | Show all commands |

## Admin Commands

| Command | Action |
|---------|--------|
| `/report` | Full team summary in chat |
| `/export` | Download CSV |

Admin dashboard: `https://yourapp.onrender.com/dashboard`

## Rules

- 4 leaves per month per employee
- Weekends auto-excluded
- Unused leaves do not carry over
- Marking closes at end of day (can't mark past dates)
# AttendBot
