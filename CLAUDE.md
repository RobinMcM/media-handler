# CLAUDE.md — media-handler

## Service Identity
FFmpeg processing service. Handles video stitching, frame extraction,
and media transformation for MovieShakerV2.
- **Framework**: FastAPI (ffmpeg-api)
- **Worker**: Shell scripts wrapping FFmpeg
- **Deployed**: Docker container

## Structure
```
ffmpeg-api/
  app/
    main.py          ← FastAPI entry point and route definitions
stitch.sh            ← FFmpeg stitch command builder
Dockerfile           ← container definition
```

## Rules — Read Before Every Task

### Scope
- Only modify the file(s) explicitly named in the request
- `stitch.sh` and `ffmpeg-api/app/main.py` are tightly coupled
- If EITHER is changed, BOTH need rebuilding — always flag this

### Git
- Do NOT run any git commands
- Developer handles all git operations

### Docker — Critical Deployment Rule
When `stitch.sh` OR `ffmpeg-api/app/main.py` is changed:
- Both the worker image AND ffmpeg-api service need rebuilding
- Suggest these commands and wait for confirmation:
  ```bash
  docker build -t media-handler .
  docker compose up -d --force-recreate --no-deps ffmpeg-api
  ```
- After rebuild, verify `/api/instructions` lists updated endpoints
- Run one live stitch/frame request before sign-off
- Do NOT run these commands automatically

### FFmpeg Commands
- Do NOT change FFmpeg command flags without explicit confirmation
- Flag any changes that could affect output format or codec compatibility
- Changes to FFmpeg commands must be tested with a real media file

### Testing
- Do NOT run any commands automatically
- Verification after changes: check `/api/instructions` then run one live request

## If Uncertain
Ask before proceeding. FFmpeg command errors can silently produce
corrupt or invalid media output.
