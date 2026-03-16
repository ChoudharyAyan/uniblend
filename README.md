# UniBlend

Blend your Spotify and YouTube Music taste into one unified playlist.

## Project structure

```
uniblend/
├── backend/          # FastAPI (Python 3.11+)
│   ├── routers/
│   │   ├── spotify.py
│   │   ├── ytmusic.py
│   │   └── blend.py
│   ├── main.py
│   ├── requirements.txt
│   └── .env          # fill in your credentials
└── frontend/         # Next.js 14 (App Router, TypeScript, Tailwind)
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   └── globals.css
    └── lib/
        └── api.ts
```

## Setup

### 1. Spotify credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create an app.
2. Set the **Redirect URI** to `http://127.0.0.1:8000/auth/spotify/callback`.
3. Copy the **Client ID** and **Client Secret** into `backend/.env`.

### 2. Backend

```bash
cd backend

# Activate the virtual environment
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies (already done if you ran the setup script)
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`.
Interactive docs: `http://127.0.0.1:8000/docs`

### 3. Frontend

> **Prerequisite:** Node.js 18+ must be installed.

```bash
cd frontend

npm install
npm run dev
```

The app will be available at `http://localhost:3000`.

## Environment variables (`backend/.env`)

| Variable | Description |
|---|---|
| `SPOTIFY_CLIENT_ID` | From Spotify Developer Dashboard |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |
| `SPOTIFY_REDIRECT_URI` | Must match what you set in Spotify dashboard |
| `GOOGLE_CLIENT_ID` | For YouTube Music OAuth (optional for now) |
| `GOOGLE_CLIENT_SECRET` | For YouTube Music OAuth (optional for now) |
| `GOOGLE_REDIRECT_URI` | Must match Google Cloud Console setting |
| `SECRET_KEY` | Random 32-char string for signing sessions |
| `FRONTEND_URL` | URL of the running frontend (default: http://localhost:3000) |

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/auth/spotify/login` | Get Spotify OAuth URL |
| GET | `/auth/spotify/callback` | OAuth callback (redirect from Spotify) |
| GET | `/spotify/me?session_id=...` | Current user profile |
| GET | `/spotify/top-tracks?session_id=...` | Top 50 tracks |
| GET | `/spotify/liked-songs?session_id=...` | Up to 200 liked songs |
| GET | `/spotify/playlists?session_id=...` | User playlists |
| GET | `/auth/ytmusic/login` | YouTube Music login (placeholder) |
| GET | `/blend/preview` | Preview blend (placeholder) |
| POST | `/blend/create` | Create blend (placeholder) |
