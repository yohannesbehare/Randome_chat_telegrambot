# 🤖 AnonChat Telegram Bot

An anonymous random chat matching bot for Telegram — similar to Omegle/Chatroulette but on Telegram. Users register profiles, get matched randomly, and chat anonymously with full admin monitoring.

## ✨ Features

- 🎭 **Fully Anonymous Chats** — users see only aliases, never real identities
- 🔀 **Random Matching** — smart queue system with gender preference support
- 📸 **Media Sharing** — photos, videos, stickers, GIFs, voice notes all supported
- 🛡️ **Mandatory Safety Warning** — sent to BOTH users every single time a chat starts
- 👁 **Admin Monitoring** — all messages relayed to admin in real-time
- 🚨 **Auto-Ban System** — users with 3+ reports are automatically banned
- 🚫 **Block System** — permanent block prevents future matching
- 🔞 **Profanity Filter** — English (extensible to Amharic)
- 🌍 **Bilingual** — English + Amharic throughout
- 📊 **Admin Dashboard** — stats, user management, broadcast, report review
- ⚡ **Rate Limiting** — 1 message/second per user
- 🔒 **Privacy Notice** — users informed chats are monitored

---

## 📁 Project Structure

```
telegram-anon-bot/
├── bot.py              # Main bot — all handlers, matching logic, admin commands
├── database.py         # SQLAlchemy models + async repository classes
├── messages.py         # All user-facing text (English + Amharic)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .env                # Your secrets (DO NOT commit this)
└── README.md           # This file
```

---

## 🚀 Setup Instructions

### 1. Prerequisites

- Python 3.10 or higher
- pip
- A Telegram account

### 2. Create Your Bot

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy your **Bot Token** (looks like `123456:ABC-DEF...`)
4. Set bot commands in BotFather with `/setcommands`:

```
search - Find a random chat partner
next - Skip to next person
end - End current chat
profile - View or edit your profile
rules - View safety rules
report - Report current user
block - Block current user
help - Show help menu
feedback - Send feedback to admin
register - Create your profile
delete - Delete your account
stop - Leave the queue
```

### 3. Get Your Telegram User ID

Message **@userinfobot** on Telegram. It will reply with your numeric user ID (e.g. `987654321`). This is your `ADMIN_TELEGRAM_ID`.

### 4. Clone & Install

```bash
# Clone or download the project
cd telegram-anon-bot

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt
```

### 5. Configure Environment

```bash
cp .env.example .env
nano .env   # or use any text editor
```

Fill in:
```env
BOT_TOKEN=your_bot_token_here
ADMIN_TELEGRAM_ID=your_telegram_user_id
DATABASE_URL=sqlite:///anonchat.db
```

### 6. Run the Bot

```bash
python bot.py
```

You should see:
```
INFO - 🚀 AnonChat Bot starting...
```

Now open Telegram, find your bot, and send `/start`.

---

## 🐘 PostgreSQL Setup (Production)

For production with many users, use PostgreSQL instead of SQLite:

```bash
# Install PostgreSQL driver
pip install asyncpg

# Set in .env:
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/anonchat
```

Create the database:
```sql
CREATE DATABASE anonchat;
CREATE USER anonchat_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE anonchat TO anonchat_user;
```

---

## 🐳 Docker Setup (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t anonchat-bot .
docker run -d --env-file .env anonchat-bot
```

---

## 🖥 Running as a Systemd Service (Linux VPS)

```ini
# /etc/systemd/system/anonchat.service
[Unit]
Description=AnonChat Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telegram-anon-bot
Environment=PATH=/home/ubuntu/telegram-anon-bot/venv/bin
ExecStart=/home/ubuntu/telegram-anon-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable anonchat
sudo systemctl start anonchat
sudo systemctl status anonchat
```

---

## 👑 Admin Commands

All admin commands only work for the Telegram account whose ID is set as `ADMIN_TELEGRAM_ID`.

| Command | Description |
|---------|-------------|
| `/stats` | Show total users, active chats, reports today, banned count |
| `/monitor` | List all currently active chats with IDs |
| `/view_chat <chat_id>` | View last 20 messages in a specific chat |
| `/users` | List all registered users (first 30) |
| `/ban <user_id> [reason]` | Ban a user immediately |
| `/unban <user_id>` | Remove a ban |
| `/reports` | View all pending reports |
| `/broadcast <message>` | Send announcement to all active users |

**Example:**
```
/ban 987654321 Sent inappropriate content
/broadcast The bot will be down for maintenance tonight at 10 PM EAT.
/view_chat a1b2c3d4e5f6
```

---

## 👤 User Flow

```
/start
  └── Not registered → /register
        └── Enter alias → age → gender → interests → bio
              └── Profile created ✅

/search
  └── Added to queue
        └── Match found → Safety Warning sent to BOTH users
              └── Chat begins (anonymous)
                    ├── /next → end chat + search again
                    ├── /end → end chat politely
                    ├── /report → report categories
                    ├── /block → block + end chat
                    └── /profile → view partner's profile
```

---

## 🛡️ Safety System

### Mandatory Warning
Every time a new chat starts, **both** users receive:

```
🛡️ SAFETY REMINDER - የደህንነት ማሳሰቢያ 🛡️

⚠️ እባኮትን ፊቶን የሚያሳይ ፎቶ ለማንም አይላኩ
Please don't send any nude photo when your face is visible

━━━━━━━━━━━━━━━━━━━━
👤 You are now chatting with: [alias]
💬 Say hello! / ሰላም በሉ!

Commands: /next | /end | /report | /block | /rules
```

### Report Categories
1. 📸 Inappropriate photo / ተገቢ ያልሆነ ፎቶ
2. 😱 Nude with face visible / ፊት የሚታይ ራቁት
3. 😡 Harassment / ትንኮሳ
4. 📢 Spam / አይፈለጌ መልእክት
5. 🎭 Fake profile / ሀሰተኛ ፕሮፋይል
6. 🔖 Other / ሌላ

### Auto-Ban
After **3 reports**, a user is automatically banned and admin is notified.

### First Photo Reminder
The first time a user sends a photo in any chat session, they receive a private reminder about not showing their face.

---

## 🔧 Customization

### Adding Amharic Profanity Words
In `bot.py`, find:
```python
AMHARIC_BAD_WORDS = []  # Add Amharic bad words here
```
Add your list:
```python
AMHARIC_BAD_WORDS = ["word1", "word2", "word3"]
```

### Changing Auto-Ban Threshold
In `bot.py`:
```python
AUTO_BAN_THRESHOLD = 3  # Change to desired number
```

### Changing Queue Match Interval
In `main()` in `bot.py`:
```python
app.job_queue.run_repeating(queue_matcher_job, interval=5, first=5)
# Change interval=5 to desired seconds
```

### Adding Gender-Based Matching Preferences
Currently users can set `pref_gender` in the DB. To expose this in the UI, add an edit option in the `/profile` command keyboard for `pref_gender`.

---

## 📊 Database Schema

| Table | Purpose |
|-------|---------|
| `users` | All registered users with profile data |
| `active_chats` | Currently ongoing and past chat sessions |
| `chat_messages` | Every forwarded message (for admin monitoring) |
| `reports` | All user reports |
| `blocked_users` | Permanent block relationships |
| `match_queue` | Users currently waiting for a match |
| `match_history` | Records of past matches (prevents re-matching) |

---

## ⚠️ Important Notes

1. **Keep `.env` secret** — never commit it to Git. Add to `.gitignore`:
   ```
   .env
   *.db
   __pycache__/
   venv/
   ```

2. **Admin monitoring** — all messages are stored in the database AND relayed to admin in real-time. Users are informed of this via the privacy notice on `/start`.

3. **Scaling** — for 1000+ concurrent users, switch to PostgreSQL and consider running on a VPS (DigitalOcean, Hetzner, etc.).

4. **python-telegram-bot v20** uses async/await throughout. Do not mix with sync code.

5. **APScheduler** (job queue) is included with `python-telegram-bot[job-queue]`. If `requirements.txt` install fails on job queue, install manually: `pip install "python-telegram-bot[job-queue]"`.

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|---------|
| `BOT_TOKEN not set` | Check your `.env` file |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Bot doesn't respond | Check token is correct; ensure bot is running |
| Queue never matches | Ensure at least 2 registered, unbanned users search |
| Admin commands don't work | Verify `ADMIN_TELEGRAM_ID` matches your Telegram ID exactly |
| `aiosqlite` error | Run `pip install aiosqlite` |
| Job queue error | Run `pip install "python-telegram-bot[job-queue]"` |

---

## 📜 License

MIT License — use freely, modify as needed.

---

## 🙏 Credits

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v20
- [SQLAlchemy](https://sqlalchemy.org/) 2.0 async
- [aiosqlite](https://github.com/omnilib/aiosqlite)
- [better-profanity](https://github.com/snguyenthanh/better_profanity)
