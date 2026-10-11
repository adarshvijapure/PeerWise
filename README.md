# StudyGroup – Peer-to-Peer Academic Q&A Platform

A focused, distraction-free study group application. No memes, no off-topic chat — just solving academic doubts.

## Features
- 🔐 **Gmail-only OAuth login** via Google
- 📚 **Study Groups** with invite-link join system
- 💬 **Threaded Queries** with open/resolved status toggle
- 📎 **Google Drive attachments** (link or direct upload)
- 🎙️ **Voice Notes** recorded in-browser (WebRTC/MediaRecorder)
- 🚨 **SOS/Urgent Mode** — instant email broadcast (3 uses/week limit)
- 🎓 **@Expert Tag** — direct email to a specific member
- 📬 **Daily Digest** — default non-spam batched emails via APScheduler

---

## Project Structure

```
studygroup/
├── run.py                        # Entry point
├── requirements.txt
├── .env.example                  # Copy to .env and fill in
├── .gitignore
└── app/
    ├── __init__.py               # App factory + APScheduler setup
    ├── config.py                 # Config from env vars
    ├── extensions.py             # db, login_manager, scheduler
    ├── models/
    │   ├── user.py               # User + SOS rate-limit logic
    │   ├── group.py              # Group + GroupMembership
    │   ├── query.py              # Query (is_urgent, tagged_expert_email)
    │   ├── reply.py              # Reply (threaded, accepted answer)
    │   └── digest_queue.py       # Daily digest pending queue
    ├── routes/
    │   ├── auth.py               # Google OAuth login/callback/logout
    │   ├── groups.py             # Group CRUD + invite
    │   ├── queries.py            # Query create/view/toggle + email routing
    │   └── replies.py            # Reply create + accept answer
    ├── services/
    │   ├── email_service.py      # Email routing gateway + digest job
    │   └── drive_service.py      # Google Drive API upload/manage
    ├── templates/
    │   ├── base.html
    │   ├── login.html
    │   ├── dashboard.html
    │   ├── groups/
    │   │   ├── create.html
    │   │   └── detail.html
    │   └── queries/
    │       ├── create.html
    │       └── detail.html
    └── static/
        ├── css/main.css
        ├── js/
        │   ├── voice_recorder.js  # WebRTC MediaRecorder
        │   └── app.js
        └── audio/                 # Voice note storage (gitignored)
```

---

## Setup

### 1. Google Cloud Console
1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Google Drive API** and **Google People API**
3. Create **OAuth 2.0 Client ID** (Web application type)
4. Add authorized redirect URI: `http://localhost:5000/auth/callback`
5. Copy Client ID and Client Secret

### 2. Gmail App Password (for SMTP)
1. Enable 2FA on your Gmail account
2. Go to **Google Account → Security → App Passwords**
3. Create an App Password for "Mail"

### 3. Environment Setup

```bash
cd studygroup
copy .env.example .env
# Edit .env with your real credentials

# Install dependencies
pip install -r requirements.txt

# Run the app
python run.py
```

Open **http://localhost:5000** in your browser.

---

## Email Routing Logic

```
New Query Created
       │
       ├── tagged_expert_email set? ──YES──► direct_tag_email() ──► instant email to that person
       │
       └── is_urgent == True? ────────YES──► urgent_broadcast_email() ──► instant email to all members
                   │                         (enforces 3/week limit per user)
                   NO
                   │
                   └──────────────────────► queue_for_digest() ──► daily 07:00 UTC batch email
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| SQLite for MVP | Zero-config, file-based, easy to migrate to Postgres later |
| Google Drive links only (no local file storage) | Keeps hosting DB/disk usage minimal |
| Authlib for OAuth | Best-in-class Flask OAuth2 library, handles PKCE, token refresh |
| APScheduler (in-process) | No external queue/worker needed for MVP |
| Voice notes stored server-side | Drive API doesn't support direct audio streaming easily |
| SOS limit = 3/week | Prevents abuse while allowing genuine urgent use |
