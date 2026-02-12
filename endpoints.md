# API Endpoints Reference

## 1. MovieShaker Engine (movieshakerv2) — port 8000

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| **GET** | `/` | No | Root; returns `{"status": "MovieShaker Engine Running", "mode": "Indie"}` |
| **GET** | `/health` | No | Health check; returns `{"status": "healthy"}` |
| **GET** | `/users` | No | List all users (SuperTokens) |
| **GET** | `/projects` | Session | List projects for the current user |
| **POST** | `/projects` | Session | Create a project |
| **PUT** | `/projects/{project_id}` | Session | Update a project (owner/editor) |
| **DELETE** | `/projects/{project_id}` | Session | Delete a project (owner only) |

**Note:** SuperTokens serves additional routes under **`/auth`** (sign up, sign in, sign out, session refresh, etc.). Exact paths are defined by the SuperTokens framework.

---

## 2. Media-handler FFmpeg API — port 8000 (separate container)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| **GET** | `/health` | No | Health check; returns `{"status": "healthy"}` |
| **GET** | `/api/instructions` | API key | List of all FFmpeg endpoints and usage |
| **GET** | `/api/logs` | API key | Last N log lines (sanitized), query: `?lines=200` (max 1000) |
| **POST** | `/api/ffmpeg/concat` | API key | Concat videos (local files in `/source`) |
| **POST** | `/api/ffmpeg/concat_spaces` | API key | Concat videos from DigitalOcean Spaces |
| **POST** | `/api/ffmpeg/trim` | API key | Trim video |
| **POST** | `/api/ffmpeg/scale` | API key | Scale video |
| **POST** | `/api/ffmpeg/crop` | API key | Crop video |
| **POST** | `/api/ffmpeg/rotate` | API key | Rotate video |
| **POST** | `/api/ffmpeg/audio` | API key | Mute/normalize audio |
| **POST** | `/api/ffmpeg/overlay` | API key | Overlay two videos |
| **POST** | `/api/ffmpeg/watermark` | API key | Add image watermark |
| **POST** | `/api/ffmpeg/encode` | API key | Encode/transcode video |
| **POST** | `/api/ffmpeg/mux` | API key | Mux one video and one audio into a single video (replace video audio with supplied audio) |

**Auth:** API key in header `X-Internal-API-Key`.

---

## Summary

- **MovieShaker engine:** 4 app routes (`/`, `/health`, `/users`, `/projects` + CRUD) plus SuperTokens under `/auth`.
- **Media-handler:** 1 unauthenticated route (`/health`) and 13 authenticated routes under `/api/...` (instructions, logs, and 11 FFmpeg operations).
