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

**Output rule (file-producing endpoints):** Job output is never written to server storage (e.g. SOURCE_DIR). For endpoints that produce a file (concat, concat_spaces, trim, scale, crop, rotate, audio, overlay, watermark, encode, mux):

- **Stream:** If the client does not provide `output_destination`, the result is returned in the HTTP response (e.g. `Content-Disposition: attachment`). The client saves to the user's machine.
- **Pre-signed URL:** If the client provides `output_destination: { "presigned_put_url": "https://..." }`, the server uploads the result to that URL with a single PUT, then returns JSON success. No S3/Spaces credentials on media-handler; the client generates the pre-signed URL.

All processing uses a temp directory under `/tmp`; the job directory is always deleted (in a `finally` block or after streaming).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| **GET** | `/health` | No | Health check; returns `{"status": "healthy"}` |
| **GET** | `/api/instructions` | API key | List of all FFmpeg endpoints and usage |
| **GET** | `/api/logs` | API key | Last N log lines (sanitized), query: `?lines=200` (max 1000) |
| **POST** | `/api/ffmpeg/concat` | API key | Concat videos (inputs from SOURCE_DIR); output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/concat_spaces` | API key | Concat videos from Spaces; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/trim` | API key | Trim video; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/scale` | API key | Scale video; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/crop` | API key | Crop video; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/rotate` | API key | Rotate video; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/audio` | API key | Mute/normalize audio; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/overlay` | API key | Overlay two videos; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/watermark` | API key | Add image watermark; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/encode` | API key | Encode/transcode video; output stream or presigned_put_url |
| **POST** | `/api/ffmpeg/mux` | API key | Mux one video and one audio; output stream or presigned_put_url |

**Auth:** API key in header `X-Internal-API-Key`.

---

## Summary

- **MovieShaker engine:** 4 app routes (`/`, `/health`, `/users`, `/projects` + CRUD) plus SuperTokens under `/auth`.
- **Media-handler:** 1 unauthenticated route (`/health`) and 13 authenticated routes under `/api/...` (instructions, logs, and 11 FFmpeg operations).
