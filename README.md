# AttendBot — Frictionless Attendance & Leave System

AttendBot is a Telegram bot + Flask web dashboard that replaces messy WhatsApp group polls. It provides employees with a frictionless, two-tap "Persistent Keyboard" to mark their daily attendance, while giving administrators a real-time, auto-refreshing web dashboard to track team presence.

## Features

* **Zero-Friction UX:** Persistent menu buttons mean employees never have to type a command.
* **Name Registration:** First-time users are prompted to enter their full legal name, so records always reflect real names — not Telegram display names.
* **Auto-Calculating Leaves:** Enforces a limit of 4 leaves/month and tracks remaining balances.
* **Weekend Awareness:** Automatically excludes Saturdays and Sundays from attendance and the dashboard.
* **Live Admin Dashboard:** Real-time KPIs, today's headcount, and a monthly visual calendar per employee.
* **CSV Export:** Admins can pull a full matrix report for payroll directly within Telegram.
* **Streak Tracking:** Consecutive present-day streaks are calculated and shown to encourage consistency.

---

## 1. Required API Keys & Environment Variables

Before running the bot, you need to gather these three environment variables:

### A. `BOT_TOKEN` (From Telegram BotFather)

This is the secret key that allows your code to control the Telegram bot.

1. Open Telegram and search for **@BotFather** (look for the verified blue checkmark).
2. Send the command `/newbot`.
3. Follow the prompts to give your bot a Display Name (e.g., `AttendBot`) and a unique username (e.g., `MyCompanyAttend_bot`).
4. BotFather will reply with a long API token that looks like `1234567890:AAH_xyz...`. Save this as your `BOT_TOKEN`.

### B. `ADMIN_IDS` (From FwebTelegram UserInfoBot)

This restricts the Dashboard, Export, and Report buttons so only administrators can see them.

1. Open Telegram and search for **@userinfobot**.
2. Send any message to it.
3. It will reply with your numeric `Id` (e.g., `123456789`).
4. Save this as your `ADMIN_IDS`. *(If you have multiple admins, separate their IDs with a comma: `123456,987654`).*

### C. `WEBHOOK_URL`

This tells Telegram exactly where to send user messages over the internet.

* **For Local Testing:** You will use an `ngrok` URL (see Local Development below).
* **For Production:** You will use your live Render URL (e.g., `https://my-attendbot.onrender.com`).

---

## 2. Local Development Setup

Because this bot uses **Webhooks**, Telegram needs a public URL to talk to your local computer. We use a free tool called [ngrok](https://ngrok.com/) to create a temporary tunnel.

1. **Clone the repository & install dependencies:**
   ```bash
   git clone https://github.com/YourUsername/AttendBot.git
   cd AttendBot
   pip install -r requirements.txt
   ```

2. **Start the ngrok tunnel:**
   *(Assuming you have downloaded and installed ngrok)*
   ```bash
   ngrok http 5000
   ```
   Copy the `Forwarding` URL it gives you (e.g., `https://a1b2c3d4.ngrok-free.app`).

3. **Set your Environment Variables (Create a `.env` file):**
   Create a file named `.env` in the root folder and add your keys:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_IDS=your_numeric_admin_id
   WEBHOOK_URL=https://a1b2c3d4.ngrok-free.app
   ```

4. **Run the local server:**
   ```bash
   python run.py
   ```

5. **Register the Webhook & Test:**
   * Open your browser and go to: `http://localhost:5000/setup` (You should see `{"description": "Webhook was set"}`).
   * Open Telegram, message your bot `/start`, and test the buttons!
   * View your local admin dashboard at `http://localhost:5000/dashboard`.

---

## 3. Deploying to Render (Free Production Server)

To keep your bot running 24/7 without your computer, deploy it to Render.com.

1. **Push your code to GitHub.** Ensure `attendance.db` and `.env` are in your `.gitignore` file.
2. Go to [Render.com](https://render.com) and create a new **Web Service**.
3. Connect your GitHub repository.
4. **Configure the Service:**
   * **Runtime:** Python 3
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn bot:app --bind 0.0.0.0:$PORT --workers 1`

5. **Set Environment Variables:** Scroll down to the Environment Variables section and add:
   * `BOT_TOKEN`: (Your BotFather Token)
   * `ADMIN_IDS`: (Your Telegram ID)
   * `WEBHOOK_URL`: `https://your-render-app-name.onrender.com` *(Make sure there is no trailing slash `/` at the end)*
   * `TZ`: `Asia/Kolkata` *(Crucial: This ensures the server calculates "midnight" correctly for attendance limits).*

6. Click **Create Web Service** and wait for the deployment to finish.
7. **Final Step (Register Production Webhook):** Once the server says "Live", open your browser and visit `https://your-render-app-name.onrender.com/setup` to link Telegram to your new cloud server.

---

## 4. How to Use

**For Employees:**
Simply share the bot's `@username` with your team.
When they press `Start`, they will be prompted to type their **full legal name**. After that, a permanent menu will appear at the bottom of their chat. They only need to tap **✅ Mark Present** or **🏖️ Take Leave** once per day.

**For Admins:**
Because your Telegram ID is in the `ADMIN_IDS` variable, your menu will automatically feature two extra buttons:

* **📋 Admin Report:** Sends a quick text summary of the whole team to your chat.
* **📥 Export CSV:** Instantly generates and downloads a spreadsheet of the month's attendance.
* **Live Dashboard:** Visit your `/dashboard` URL in any web browser for the full visual experience.

*(Note: To easily test the dashboard visuals, you can instantly populate the database with fake employees by visiting `/demo/seed` in your browser).*

---

## Project Structure

```
attendance_system/
├── bot.py             # Main application (bot logic + dashboard HTML)
├── run.py             # Local dev runner with debug mode
├── requirements.txt   # Python dependencies (Flask, requests)
├── .env               # Environment variables (not committed)
├── .gitignore         # Excludes .env, attendance.db, __pycache__
└── attendance.db      # SQLite database (auto-created at runtime)
```

## Tech Stack

* **Backend:** Python 3, Flask
* **Bot API:** Telegram Bot API (webhooks)
* **Database:** SQLite
* **Dashboard:** Vanilla HTML/CSS/JS (embedded in bot.py)
* **Hosting:** Render.com (free tier)