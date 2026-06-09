<div align="center">

# AttendBot
**Frictionless Attendance & Leave System**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram API" />
  <img src="https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" alt="Render" />
</p>

**Live Bot:** [@tetris_tkhub_bot](https://t.me/tetris_tkhub_bot) | **Live Dashboard:** [View Demo](https://attendbot-demo.onrender.com/dashboard) 
*(Evaluator Admin Access: Type `/admin attendbot123` in the bot)*

</div>

---

## Features

| **1-Tap Actions** | **Smart Leave Tracking** | **Weekend Aware** |
| :---: | :---: | :---: |
| **Live Dashboard** | **Instant Export** | **Data Safe** |

## Environment Variables

Create a `.env` file with the following variables:

| Variable | Example Value |
| :--- | :--- |
| `BOT_TOKEN` | your_bot_token_from_botfather |
| `ADMIN_IDS` | 123456789,987654321 |
| `ADMIN_PASSWORD` | attendbot123 |
| `WEBHOOK_URL` | https://your-public-url.com |
| `DATABASE_URL` | postgresql://user:pass@host/dbname |
| `TZ` | Asia/Kolkata |


### Local Development
1. **Clone the repository and install dependencies:**
   ```bash
   git clone [https://github.com/GaneshAdimalupu/AttendBot.git](https://github.com/GaneshAdimalupu/AttendBot.git)
   cd AttendBot
   pip install -r requirements.txt
   ```

2. **Start an `ngrok` tunnel to get a public HTTPS URL:**
   ```bash
   ngrok http 5000
   ```
   *(Update your `.env` `WEBHOOK_URL` with the generated ngrok URL).*

3. **Run the bot:**
   ```bash
   python bot.py
   ```

4. **Activate the webhook:**
   Visit `http://localhost:5000/setup` in your browser.

## 🚀 Production Deployment

For instructions on deploying the application to cloud hosting platforms (e.g., Render) using a PostgreSQL database, please check the [DEPLOYMENT.md](DEPLOYMENT.md) guide.

## Usage Guide

| Category | Details |
| :--- | :--- |
| **Employees** | Send `/start`, enter your name, and use the persistent bottom menu to mark presence or leave daily. |
| **Admins** | If your ID is in `ADMIN_IDS` (or you unlock via `/admin attendbot123`), you can pull **Reports**, **Export CSVs**, look up employees with `/whois`, archive them with `/remove`, view them with `/archived`, restore them with `/restore`, and broadcast messages. |
| **Holiday Management** | Admins can register public holidays to automatically block attendance marking and reminders. Supports both single dates and date ranges (e.g. Christmas/Puja week blocks) via bot commands or the dashboard UI. |
| **Commands** | `/start`, `/help`, `/status`, `/leaves`, `/rename`, `/report`, `/export`, `/whois`, `/remove`, `/archived`, `/restore`, `/broadcast`, `/admin`, `/holidays`, `/addholiday`, `/removeholiday` |
| **Test Data** | Visit `https://your-url.com/demo/seed` to instantly fill the database with realistic dummy data for dashboard evaluation. |

### Holiday Command Examples:
- **List holidays:** `/holidays`
- **Add single day:** `/addholiday 2026-06-15 Eid al-Adha`
- **Add date range:** `/addholiday 2026-10-20 to 2026-10-22 Puja Holidays` (also accepts `-` or `/` separators)
- **Remove single day:** `/removeholiday 2026-06-15`
- **Remove date range:** `/removeholiday 2026-10-20 to 2026-10-22`