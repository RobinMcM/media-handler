# CLAUDE.md — media-handler

## Service Identity
FFmpeg execution API. Accepts video processing requests and executes
FFmpeg commands via Docker. Returns results as streaming file download
or uploads to a caller-provided presigned URL.

**This is a stateless dumb handler.** It does not store files, track jobs,
or manage state. All output goes directly to the caller or to a
presigned upload URL. The only exception is frame extraction which
writes to DigitalOcean Spaces.

- **Language**: Python 3.11
- **Framework**: FastAPI
- **FFmpeg**: Executed via Docker (`docker run media-handler`)
- **Rate limiting / deduplication**: Valkey guard
- **Frame storage**: DigitalOcean Spaces (extract-frame only)
- **CORS**: Handled by Nginx
- **Deployed at**: `https://media.rapidmvp.io` (DigitalOcean Droplet)

## Structure
```
ffmpeg-api/
  app/
    main.py          ← entry point, all route registrations
    schemas.py       ← all Pydantic request/response models
    ffmpeg.py        ← FFmpeg command builders (one per operation)
    auth.py          ← API key verification
    docker_exec.py   ← Docker + FFmpeg execution layer
    logger.py        ← structured logging
    spaces.py        ← DigitalOcean Spaces (upload/download/URL)
    download.py      ← URL download utilities
    valkey_guard.py  ← rate limiting and deduplication via Valkey
nginx/
  conf.d/
    media.rapidmvp.io.conf  ← HTTPS + CORS config
stitch.sh                   ← legacy FFmpeg stitch script
```

## Rules — Read Before Every Task

### Scope
- Only modify the file(s) explicitly named in the request
- `ffmpeg.py` and `main.py` are tightly coupled — if either changes,
  both may need updating. Always flag this.
- Do not modify `nginx/` without explicit confirmation
- Do not modify `valkey_guard.py` without explicit confirmation

### Git
- Do NOT run any git commands
- Developer handles all git operations

### Docker — Critical Rebuild Rule
When `stitch.sh` OR any file in `ffmpeg-api/app/` changes:
- Suggest these commands and wait for confirmation:
  ```bash
  docker build -t media-handler .
  docker compose up -d --force-recreate --no-deps ffmpeg-api
  ```
- Verify `/api/instructions` lists updated endpoints after rebuild
- Run one live request before sign-off
- Do NOT run these automatically

### FFmpeg Commands
- Never change FFmpeg flags without explicit confirmation
- Changes to FFmpeg commands must be tested with real media
- Flag any change that could affect output format or codec compatibility

### Output Rule — Critical
Job output is NEVER written to server storage (SOURCE_DIR).
For file-producing endpoints either:
1. File is streamed in the response (no `output_destination`)
2. Client provides `output_destination.presigned_put_url` and result
   is uploaded there via PUT — then JSON success is returned

### Testing
- Do NOT run tests automatically
- Frame extraction test: `python3 ffmpeg-api/scripts/test_mux.py`
- Valkey guard test: `python3 ffmpeg-api/scripts/verify_valkey_guard.py`

## Current FFmpeg Endpoints

| Method | Path | Operation |
|--------|------|-----------|
| GET | `/health` | Liveness check |
| GET | `/api/instructions` | Full API documentation |
| GET | `/api/logs` | Sanitised logs |
| POST | `/api/ffmpeg/concat` | Concatenate videos (local files) |
| POST | `/api/ffmpeg/concat-spaces` | Concatenate videos (from DO Spaces) |
| POST | `/api/ffmpeg/trim` | Trim by start/end time |
| POST | `/api/ffmpeg/scale` | Scale to size |
| POST | `/api/ffmpeg/crop` | Crop to rectangle |
| POST | `/api/ffmpeg/rotate` | Rotate (90/180/270) |
| POST | `/api/ffmpeg/audio` | Mute or normalise audio |
| POST | `/api/ffmpeg/overlay` | Overlay video on video |
| POST | `/api/ffmpeg/watermark` | Add image watermark |
| POST | `/api/ffmpeg/encode` | Transcode to format/codec |
| POST | `/api/ffmpeg/mux` | Mux video + audio tracks |
| POST | `/api/ffmpeg/extract-last-frame` | Extract frame → Spaces URL |
| POST | `/api/ffmpeg/extract_frame` | Legacy alias |
| POST | `/api/ffmpeg/last-frame` | Legacy alias |

## Missing FFmpeg Operations (Future Build Targets)
These standard FFmpeg operations are not yet implemented:

- **probe / info** — get video metadata (duration, codec, resolution, fps)
- **thumbnail-grid** — extract multiple frames as a contact sheet
- **speed** — change playback speed (fast/slow motion)
- **reverse** — reverse video playback
- **fade** — fade in/out at start/end
- **subtitle** — burn in subtitles/captions (SRT/ASS)
- **audio-extract** — extract audio track as mp3/aac
- **audio-replace** — replace audio track on a video
- **stabilize** — video stabilisation
- **split** — split video at timestamp into two files
- **gif** — convert video clip to GIF

These are tracked as Phase 4 build targets.

## Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `FFMPEG_API_KEY` | ✅ | Auth key for all `/api/*` endpoints |
| `SOURCE_DIR` | | Working directory for input files |
| `DO_SPACES_ENDPOINT` | | DigitalOcean Spaces endpoint |
| `DO_SPACES_REGION` | | Spaces region |
| `DO_SPACES_BUCKET` | | Spaces bucket name |
| `DO_SPACES_ACCESS_KEY_ID` | | Spaces access key |
| `DO_SPACES_SECRET_ACCESS_KEY` | | Spaces secret key |
| `SPACES_PUBLIC_BASE_URL` | | Public base URL for uploaded assets |
| `VALKEY_URL` | | Valkey connection URL for rate limiting |

## If Uncertain
Ask before proceeding. Do not infer intent and act.
FFmpeg command errors can silently produce corrupt or invalid media output.
One task at a time. Wait for confirmation before the next step.
