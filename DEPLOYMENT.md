# 🚀 Deploying AttendBot

This guide provides step-by-step instructions for deploying AttendBot to production using **Render** and **PostgreSQL**.

---

## 📋 Table of Contents
1. [Prerequisites](#-1-prerequisites)
2. [Database Setup (Render PostgreSQL)](#-2-database-setup-render-postgresql)
3. [Web Service Setup (Render)](#-3-web-service-setup-render)
4. [Environment Variables](#-4-environment-variables)
5. [Activating the Webhook](#-5-activating-the-webhook)

---

## 🔑 1. Prerequisites

Before starting, ensure you have:
* A **GitHub** account with a fork/clone of this repository.
* A **Render** account ([render.com](https://render.com)).
* A **Telegram Bot Token** (obtain from [@BotFather](https://t.me/BotFather) by running `/newbot`).
* Your Telegram User ID (obtain from [@userinfobot](https://t.me/userinfobot)) to set as the Admin.

---

## 🗄️ 2. Database Setup (Render PostgreSQL)

AttendBot uses PostgreSQL for persistent data storage.

1. Log in to your **Render Dashboard**.
2. Click **New +** and select **PostgreSQL**.
3. Configure the database details:
   * **Name**: `attendbot-db`
   * **Region**: Select a region close to you or your target users (e.g., `Singapore`).
   * **Database**: `attendbot`
   * **User**: `attendadmin`
4. Choose the **Free** instance type (or any tier of your choice).
5. Click **Create Database**.
6. Once the database status changes to **Available**, copy the **Internal Database URL** (or **External Database URL** if you need to connect from outside Render).

---

## ☁️ 3. Web Service Setup (Render)

Deploy the Flask application to handle incoming Telegram webhooks and serve the web dashboard.

1. On your Render Dashboard, click **New +** and select **Web Service**.
2. Connect your GitHub repository.
3. Configure the web service details:
   * **Name**: `attendbot-service`
   * **Region**: Match the database region (e.g., `Singapore`).
   * **Branch**: `main` (or the branch containing your production code).
   * **Runtime**: `Python 3`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `gunicorn run:app`
4. Choose the **Free** instance type.
5. Expand the **Advanced** section to add the environment variables listed below.
6. Click **Create Web Service**.

---

## ⚙️ 4. Environment Variables

Add these variables to your Render Web Service configurations (**Environment** tab):

| Variable | Description | Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | The PostgreSQL Connection String (Internal Database URL from Step 2) | `postgres://user:pass@host/dbname` |
| `BOT_TOKEN` | Your Telegram Bot Token | `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ` |
| `ADMIN_IDS` | Comma-separated list of Telegram User IDs allowed to access admin reports/exports | `987654321` |
| `ADMIN_PASSWORD` | Fallback password for evaluators/admins to authenticate via `/admin password` | `attendbot123` |
| `WEBHOOK_URL` | The public URL of your Render web service (no trailing slash) | `https://attendbot-service.onrender.com` |
| `TZ` | Timezone database string to ensure correct date-resets | `Asia/Kolkata` |

---

## ⚡ 5. Activating the Webhook

Telegram needs to know where to send incoming updates.

1. Wait for your Render Web Service build to finish and show a status of **Live**.
2. Open your web browser and visit:
   ```
   https://your-service-name.onrender.com/setup
   ```
3. You should see a JSON response confirming that the webhook was successfully registered:
   ```json
   {
     "webhook": {
       "description": "Webhook was set",
       "ok": true,
       "result": true
     },
     "commands": {
       "ok": true,
       "result": true
     }
   }
   ```
4. Send `/start` to your Telegram Bot to initialize your registration!
