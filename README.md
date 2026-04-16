# Media Handler

FFmpeg execution API for MovieShaker.
Accepts video processing requests, executes FFmpeg via Docker,
and returns results as a streaming download or presigned upload.

**Stateless.** No file storage on the server. All output goes directly
to the caller or to a caller-provided presigned URL.

## Setup

### Environment Variables

```bash
FFMPEG_API_KEY=your-secret-key
SOURCE_DIR=/path/to/working/dir

# DigitalOcean Spaces (required for extract-frame)
DO_SPACES_ENDPOINT=https://lon1.digitaloceanspaces.com
DO_SPACES_REGION=lon1
DO_SPACES_BUCKET=your-bucket
DO_SPACES_ACCESS_KEY_ID=your-key
DO_SPACES_SECRET_ACCESS_KEY=your-secret
SPACES_PUBLIC_BASE_URL=https://your-bucket.lon1.digitaloceanspaces.com

# Optional
VALKEY_URL=redis://localhost:6379
```

### Run

```bash
docker compose up -d --build
```

## Authentication

All `/api/*` endpoints require:
```
X-API-Key: your-secret-key
```

Only `GET /health` is unauthenticated.

## Output Handling

Every file-producing endpoint works in two modes:

**Stream mode** (no `output_destination`):
```json
{ "inputs": ["a.mp4", "b.mp4"], "output": "out.mp4" }
```
Returns the file as a streaming download.

**Presigned upload mode**:
```json
{
  "inputs": ["a.mp4", "b.mp4"],
  "output": "out.mp4",
  "output_destination": { "presigned_put_url": "https://..." }
}
```
Uploads result to the presigned URL, returns `{"status": "ok"}`.

The caller generates the presigned URL. No storage credentials on this server.

## Current Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/api/instructions` | Full API documentation |
| GET | `/api/logs` | Sanitised logs |
| POST | `/api/ffmpeg/concat` | Concatenate videos (local files) |
| POST | `/api/ffmpeg/concat-spaces` | Concatenate videos (from DO Spaces) |
| POST | `/api/ffmpeg/trim` | Trim by start/end time or duration |
| POST | `/api/ffmpeg/scale` | Scale to target size |
| POST | `/api/ffmpeg/crop` | Crop to rectangle |
| POST | `/api/ffmpeg/rotate` | Rotate 90/180/270 degrees |
| POST | `/api/ffmpeg/audio` | Mute or normalise audio |
| POST | `/api/ffmpeg/overlay` | Overlay video on video |
| POST | `/api/ffmpeg/watermark` | Add image watermark |
| POST | `/api/ffmpeg/encode` | Transcode to format/codec |
| POST | `/api/ffmpeg/mux` | Mux video + audio tracks |
| POST | `/api/ffmpeg/extract-last-frame` | Extract frame → Spaces URL |

## Example: Concatenate

```bash
curl -X POST https://media.rapidmvp.io/api/ffmpeg/concat \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": ["clip1.mp4", "clip2.mp4"],
    "output": "final.mp4"
  }' \
  --output final.mp4
```

## Example: Extract Frame

```bash
curl -X POST https://media.rapidmvp.io/api/ffmpeg/extract-last-frame \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "position": "last"
  }'
# → { "status": "ok", "image_url": "https://..." }
```

## Planned Endpoints (Phase 4)

These FFmpeg operations are not yet implemented:

| Operation | Description |
|-----------|-------------|
| `probe` | Get video metadata (duration, codec, resolution, fps) |
| `thumbnail-grid` | Extract multiple frames as contact sheet |
| `speed` | Change playback speed (fast/slow motion) |
| `reverse` | Reverse video playback |
| `fade` | Fade in/out at start/end |
| `subtitle` | Burn in subtitles/captions (SRT/ASS) |
| `audio-extract` | Extract audio track as mp3/aac |
| `audio-replace` | Replace audio track on a video |
| `split` | Split video at timestamp into two files |
| `gif` | Convert video clip to animated GIF |

## Deployment

Deployed at `https://media.rapidmvp.io` on a DigitalOcean Droplet.
HTTPS and CORS managed by Nginx.

After any code change:
```bash
docker build -t media-handler .
docker compose up -d --force-recreate --no-deps ffmpeg-api
```

Verify with:
```bash
curl https://media.rapidmvp.io/health
curl -H "X-API-Key: your-key" https://media.rapidmvp.io/api/instructions
```
