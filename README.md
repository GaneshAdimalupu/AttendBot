# 📋 AttendBot — Frictionless Attendance & Leave System

AttendBot is a Telegram bot + Flask web dashboard that replaces messy WhatsApp group polls. It provides employees with a frictionless, two-tap "Persistent Keyboard" to mark their daily attendance, while giving administrators a real-time, auto-refreshing web dashboard to track team presence.

**Live Prototype:** [@tetris_tkhub_bot](https://t.me/tetris_tkhub_bot)  
**Live Dashboard:** [https://attendbot-demo.onrender.com/dashboard](https://attendbot-demo.onrender.com/dashboard)  
**Evaluator Access:** Type `/admin attendbot123` in the bot to instantly unlock admin features.

## ✨ Features
* **Zero-Friction UX:** Persistent menu buttons mean employees never have to type a command.
* **Auto-Calculating Leaves:** Enforces a limit of 4 leaves/month and tracks remaining balances.
* **Weekend Awareness:** Automatically excludes Saturdays and Sundays.
* **Live Admin Dashboard:** Real-time KPIs, today's headcount, and a monthly visual calendar.
* **CSV Export:** Admins can pull a full matrix report for payroll directly within Telegram.
* **Production Ready:** Backed by PostgreSQL to ensure zero data loss during server restarts.

---

## 🔑 1. Required Environment Variables

Before running the bot, you need to gather these variables:

* **`BOT_TOKEN`**: From Telegram [@BotFather](https://t.me/BotFather). Send `/newbot` to generate a token.
* **`ADMIN_IDS`**: From Telegram [@userinfobot](https://t.me/userinfobot). This restricts Admin-only buttons. (Separate multiple IDs with commas).
* **`ADMIN_PASSWORD`**: A fallback password (e.g., `attendbot123`) for evaluators to gain admin access.
* **`WEBHOOK_URL`**: The public URL of your server (e.g., `https://attendbot-demo.onrender.com` or an ngrok URL for local testing).
* **`DATABASE_URL`**: Your PostgreSQL connection string.
* **`TZ`**: Timezone (e.g., `Asia/Kolkata`) to ensure daily attendance resets happen at the correct midnight.

---

## ☁️ 2. Production Deployment (Render)

This project includes a `render.yaml` Blueprint, making cloud deployment fully automated.

1. Fork or clone this repository to your GitHub account.
2. Go to [Render.com](https://render.com) and log in.
3. Click **New +** and select **Blueprint**.
4. Connect your GitHub repository.
5. Render will detect the `render.yaml` file and prompt you to enter the secure environment variables (`BOT_TOKEN`, `ADMIN_IDS`, `WEBHOOK_URL`).
6. Click **Apply**.

Render will automatically provision the PostgreSQL database, link it to the web service, install dependencies, and launch the bot.  
*Note: Make sure your `WEBHOOK_URL` does not have a trailing slash.*

**Final Step:** Once the server is live, visit `https://your-app.onrender.com/setup` in your web browser to securely link Telegram to your new server.

---

## 💻 3. Local Development Setup

To test the bot locally, Telegram requires a public HTTPS URL to send webhooks to. We use [ngrok](https://ngrok.com/) to create a temporary tunnel to your local machine.

1. **Clone the repository & install dependencies:**
   ```bash
   git clone https://github.com/GaneshAdimalupu/AttendBot.git
   cd AttendBot
   pip install -r requirements.txt
   ```

2. **Start the ngrok tunnel:**
   ```bash
   ngrok http 5000
   ```
   *Copy the `Forwarding` URL it gives you (e.g., `https://a1b2c3d4.ngrok-free.app`).*

3. **Set your Environment Variables:**
   Create a `.env` file in the root directory:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_IDS=your_numeric_admin_id
   ADMIN_PASSWORD=attendbot123
   WEBHOOK_URL=https://a1b2c3d4.ngrok-free.app
   DATABASE_URL=postgresql://user:password@localhost:5432/attendbot
   TZ=Asia/Kolkata
   ```

4. **Run the local server:**
   ```bash
   python bot.py
   ```

5. **Register the Webhook:**
   Open your browser and visit: `http://localhost:5000/setup`. You should see a success message from Telegram.

---

## 👥 4. How to Use

**For Employees:**
Share the bot's `@username` with your team.
When they press `/start`, they will be prompted to type their legal name. After that, a permanent menu will appear at the bottom of their chat. They only need to tap **✅ Mark Present** or **🏖️ Take Leave** once per day.

**For Admins:**
Because your Telegram ID is in the `ADMIN_IDS` variable (or you entered the `/admin` password), your menu will automatically feature two extra buttons:

* **📋 Admin Report:** Sends a quick text summary of the whole team to your chat.
* **📥 Export CSV:** Instantly generates and downloads a spreadsheet of the month's attendance.

**Dashboard Demo:**
To easily test the dashboard visuals during evaluation, visit `https://your-app-url.onrender.com/demo/seed` in your browser. This will instantly populate the database with realistic, randomized employee data for the current month.