# Implementation Plan: /api/instructions + /api/logs + AI Rules

## ✅ Plan Updated Based on Feedback (2026-01-10)

### Changes Applied

**1. ❌ Removed: Logging from main.py**
- **Problem:** Original plan logged from `main.py` with fake job IDs like `"pre-execution"`
- **Solution:** All logging now happens ONLY in `docker_exec.py` where real `job_id` exists
- **Why:** Prevents duplicate/misleading logs that confuse debugging

**2. ✅ Improved: Path Sanitization Strategy**
- **Problem:** "Replace file paths with just filenames" could break debugging
- **Solution:** 
  - Redact host absolute paths: `/source/file.mp4` → `[HOST_PATH_REDACTED]`
  - Preserve container paths: `/videos/file.mp4` (keep for debugging)
  - Keep mount structure visible: `-v [HOST_PATH_REDACTED]:/videos`
- **Example log:** `docker run --rm -v [HOST_PATH_REDACTED]:/videos media-handler concat a.mp4 b.mp4 out.mp4`
- **Why:** Balances security with operational debuggability

**3. ✅ Fixed: Pydantic Dict Defaults**
- **Problem:** `auth: dict = {"header": "X-Internal-API-Key"}` causes linting issues (mutable default)
- **Solution:** `auth: Dict[str, str] = Field(default_factory=lambda: {"header": "X-Internal-API-Key"})`
- **Why:** Follows Pydantic best practices, avoids linter warnings

**4. ✅ Added: /health Endpoint to Documentation**
- **Included:** `/health` endpoint now documented in `/api/instructions` response
- **Marked as:** "Unauthenticated health check for monitoring"
- **Why:** Internal ops teams need complete API reference, even for unauthenticated endpoints

---

## Project Overview
**Target**: `/root/media-handler/ffmpeg-api/`  
**Service**: Internal-only FastAPI wrapper for FFmpeg Docker worker  
**Current Dependencies**: FastAPI 0.109.0, Uvicorn 0.27.0, Pydantic 2.5.3

---

## Current Architecture Analysis

### Existing Files
```
/root/media-handler/ffmpeg-api/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app with 9 FFmpeg endpoints
│   ├── auth.py           # X-Internal-API-Key authentication
│   ├── schemas.py        # Pydantic models for requests/responses
│   ├── ffmpeg.py         # FFmpeg command builders
│   └── docker_exec.py    # Docker execution logic
├── Dockerfile
└── requirements.txt
```

### Existing Endpoints
1. `POST /api/ffmpeg/concat` - Concatenate videos
2. `POST /api/ffmpeg/trim` - Trim video segments
3. `POST /api/ffmpeg/scale` - Scale video resolution
4. `POST /api/ffmpeg/crop` - Crop video dimensions
5. `POST /api/ffmpeg/rotate` - Rotate video
6. `POST /api/ffmpeg/audio` - Audio operations (mute/normalize)
7. `POST /api/ffmpeg/overlay` - Overlay videos
8. `POST /api/ffmpeg/watermark` - Add watermark to video
9. `POST /api/ffmpeg/encode` - Encode/transcode video
10. `GET /health` - Health check (no auth required)

### Authentication Flow
- All `/api/ffmpeg/*` endpoints use `Depends(verify_api_key)`
- Header: `X-Internal-API-Key`
- Valid keys loaded from env var: `INTERNAL_API_KEYS` (comma-separated)

---

## Key Implementation Decisions

### ✅ Best Practices Applied

1. **Single-Point Logging**
   - All logging happens in `docker_exec.py` where real `job_id` is generated
   - **NO logging in `main.py`** - prevents duplicate/misleading logs
   - Maintains clear debugging trail with consistent job IDs

2. **Smart Path Sanitization**
   - Redact host absolute paths (`/source/...`, `/root/...`)
   - **Preserve container paths** (`/videos/...`) for debugging
   - Keep mount structure visible: `-v [HOST_PATH_REDACTED]:/videos`
   - Example: `docker run --rm -v [HOST_PATH_REDACTED]:/videos media-handler concat a.mp4 b.mp4 out.mp4`
   - **Why:** Balances security with operational debuggability

3. **Pydantic Best Practices**
   - Use `Field(default_factory=lambda: {...})` for dict defaults
   - Avoid mutable defaults that cause linting issues
   - Explicitly type dicts as `Dict[str, Any]`

4. **Complete API Documentation**
   - Include all 10 endpoints (9 FFmpeg + `/health`)
   - Document `/health` as "unauthenticated health check"
   - **Why:** Internal ops teams need complete API reference for monitoring

---

## TASK 1: Implement Logging System

### Goal
Add minimal logging to `/tmp/ffmpeg-api.log` for operational debugging

### Implementation Details

#### 1.1 Create Logger Module (`app/logger.py`)
```
Location: /root/media-handler/ffmpeg-api/app/logger.py
```

**Responsibilities:**
- Configure Python's standard `logging` module (NO external frameworks)
- Append to `/tmp/ffmpeg-api.log` (create if not exists)
- Format: `YYYY-MM-DDTHH:MM:SSZ LEVEL message`
- Include functions:
  - `log_request(endpoint, job_id)`
  - `log_docker_command(job_id, command_sanitized)`
  - `log_success(job_id, output_file)`
  - `log_error(job_id, stderr_truncated)`
  - `sanitize_command(command)` - remove sensitive data before logging

**Sanitization Rules:**
- Never log actual API key values
- Redact host absolute paths (e.g., `/source/...`, `/root/...`) but preserve container paths (`/videos/...`)
- Keep mount structure visible for debugging: `-v [HOST_PATH_REDACTED]:/videos`
- Preserve basenames and container arguments for debugging
- Truncate stderr to 8KB max
- Redact any patterns matching: `key=`, `token=`, `secret=`, signed URLs

**Example sanitized log:**
```
docker run --rm -v [HOST_PATH_REDACTED]:/videos media-handler concat a.mp4 b.mp4 out.mp4
```

**Configuration:**
```python
LOG_FILE = "/tmp/ffmpeg-api.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_STDERR_LENGTH = 8192
```

#### 1.2 Integrate Logging into `docker_exec.py`

**Changes to `execute_ffmpeg_command()` function:**

1. **At start of function:**
   - Log: `log_request("ffmpeg", job_id)`

2. **Before docker execution:**
   - Log: `log_docker_command(job_id, sanitize_command(docker_cmd))`

3. **On success (line 46-49):**
   - Log: `log_success(job_id, output_file)`

4. **On error (line 51):**
   - Log: `log_error(job_id, result.stderr[:8192])`

5. **On timeout (line 54):**
   - Log: `log_error(job_id, "Command timed out after 1 hour")`

6. **On exception (line 56):**
   - Log: `log_error(job_id, str(e))`

**No changes to function signature or return values**

**Important:** Do NOT add logging to `main.py` endpoints. All logging happens in `docker_exec.py` where the real `job_id` is generated. Logging from `main.py` with fake job IDs would create duplicate/misleading logs that confuse debugging.

---

## TASK 2: Implement GET /api/instructions

### Goal
Provide API documentation for all existing endpoints

### Implementation Details

#### 2.1 Create Endpoint in `main.py`

**Location:** `/root/media-handler/ffmpeg-api/app/main.py`  
**Insert after:** Line 16 (after `app = FastAPI(...)`)

**Route signature:**
```python
@app.get("/api/instructions", response_model=InstructionsResponse)
async def get_instructions(api_key: str = Depends(verify_api_key)):
```

#### 2.2 Create Response Schema

**Location:** `/root/media-handler/ffmpeg-api/app/schemas.py`  
**Add at end of file:**

```python
from pydantic import Field
from typing import Any, Dict

class EndpointInfo(BaseModel):
    name: str
    method: str
    path: str
    description: str
    request_body: Dict[str, Any]
    success_response: Dict[str, Any]
    error_response: Dict[str, Any]

class InstructionsResponse(BaseModel):
    status: str = "ok"
    service: str = "ffmpeg-api"
    auth: Dict[str, str] = Field(default_factory=lambda: {"header": "X-Internal-API-Key"})
    endpoints: List[EndpointInfo]
```

**Note:** Using `Field(default_factory=...)` instead of mutable dict defaults avoids Pydantic linting issues and follows best practices.

#### 2.3 Endpoint Documentation Content

**For each of 10 endpoints, include:**

1. **concat:**
   - name: "concat"
   - method: "POST"
   - path: "/api/ffmpeg/concat"
   - description: "Concatenate multiple video files into one"
   - request_body: `{"inputs": ["a.mp4", "b.mp4"], "output": "out.mp4"}`
   - success_response: `{"status": "ok", "output": "out.mp4"}`
   - error_response: `{"status": "error", "message": "..."}`

2. **trim:**
   - name: "trim"
   - method: "POST"
   - path: "/api/ffmpeg/trim"
   - description: "Trim video by start/end time or duration"
   - request_body: `{"input": "video.mp4", "output": "trimmed.mp4", "start": 10.5, "end": 30.0}` (or "duration": 19.5)
   - success_response: same as concat
   - error_response: same as concat

3. **scale:**
   - name: "scale"
   - method: "POST"
   - path: "/api/ffmpeg/scale"
   - description: "Scale video to specified size"
   - request_body: `{"input": "video.mp4", "output": "scaled.mp4", "size": "1280x720", "aspect_ratio": false}`
   - success_response: same
   - error_response: same

4. **crop:**
   - name: "crop"
   - method: "POST"
   - path: "/api/ffmpeg/crop"
   - description: "Crop video to specified rectangle"
   - request_body: `{"input": "video.mp4", "output": "cropped.mp4", "x": 0, "y": 0, "width": 640, "height": 480}`
   - success_response: same
   - error_response: same

5. **rotate:**
   - name: "rotate"
   - method: "POST"
   - path: "/api/ffmpeg/rotate"
   - description: "Rotate video by specified angle (90, 180, 270)"
   - request_body: `{"input": "video.mp4", "output": "rotated.mp4", "angle": 90}`
   - success_response: same
   - error_response: same

6. **audio:**
   - name: "audio"
   - method: "POST"
   - path: "/api/ffmpeg/audio"
   - description: "Process audio (mute or normalize)"
   - request_body: `{"input": "video.mp4", "output": "muted.mp4", "action": "mute", "normalize": false}`
   - success_response: same
   - error_response: same

7. **overlay:**
   - name: "overlay"
   - method: "POST"
   - path: "/api/ffmpeg/overlay"
   - description: "Overlay one video on top of another"
   - request_body: `{"base": "background.mp4", "overlay": "foreground.mp4", "output": "result.mp4", "x": 0, "y": 0}`
   - success_response: same
   - error_response: same

8. **watermark:**
   - name: "watermark"
   - method: "POST"
   - path: "/api/ffmpeg/watermark"
   - description: "Add image watermark to video"
   - request_body: `{"video": "input.mp4", "image": "logo.png", "output": "watermarked.mp4", "position": "top-right", "opacity": 0.8}`
   - (alternative: use "x": 10, "y": 10 instead of "position")
   - success_response: same
   - error_response: same

9. **encode:**
   - name: "encode"
   - method: "POST"
   - path: "/api/ffmpeg/encode"
   - description: "Encode/transcode video to different format or codec"
   - request_body: `{"input": "video.mp4", "output": "encoded.webm", "format": "webm", "vcodec": "libvpx", "acodec": "libvorbis"}`
   - success_response: same
   - error_response: same

10. **health:**
   - name: "health"
   - method: "GET"
   - path: "/health"
   - description: "Unauthenticated health check for monitoring"
   - request_body: None (GET request, no body)
   - success_response: `{"status": "healthy"}`
   - error_response: N/A
   - **Note:** This endpoint does NOT require X-Internal-API-Key authentication

**Rationale for including /health:** While it doesn't require auth, internal ops teams will use it for monitoring and service discovery. Including it in instructions provides complete API documentation.

---

## TASK 3: Implement GET /api/logs

### Goal
Return recent operational logs for debugging

### Implementation Details

#### 3.1 Create Endpoint in `main.py`

**Location:** `/root/media-handler/ffmpeg-api/app/main.py`  
**Insert after:** `/api/instructions` endpoint

**Route signature:**
```python
@app.get("/api/logs", response_model=LogsResponse)
async def get_logs(
    lines: int = 200,
    api_key: str = Depends(verify_api_key)
):
```

#### 3.2 Create Response Schema

**Location:** `/root/media-handler/ffmpeg-api/app/schemas.py`  
**Add after `InstructionsResponse`:**

```python
class LogsResponse(BaseModel):
    status: str = "ok"
    lines: int
    logs: List[str]
```

#### 3.3 Implementation Logic

**Pseudocode:**
```python
1. Validate lines parameter:
   - Default: 200
   - Max: 1000
   - If lines > 1000, set lines = 1000

2. Check if /tmp/ffmpeg-api.log exists:
   - If NOT exists: return {"status": "ok", "lines": 0, "logs": []}

3. Read last N lines from file:
   - Use efficient tail reading (don't load entire file)
   - Implementation: read file in reverse or use collections.deque

4. Sanitize log lines:
   - Redact any X-Internal-API-Key values
   - Redact patterns: key=*, token=*, secret=*
   - Redact signed URLs (anything with ?signature= or similar)
   - Replace with "[REDACTED]"

5. Return response:
   - {"status": "ok", "lines": <actual_count>, "logs": [...]}
```

#### 3.4 Create Log Reader Utility

**Location:** `/root/media-handler/ffmpeg-api/app/logger.py`  
**Add function:**

```python
def read_last_n_lines(filepath: str, n: int) -> List[str]:
    """Read last N lines from log file efficiently"""
    # Implementation using deque or reverse reading
    
def sanitize_log_line(line: str) -> str:
    """Remove sensitive data from log line"""
    # Redact patterns:
    # - X-Internal-API-Key: xxxxxx -> X-Internal-API-Key: [REDACTED]
    # - key=value -> key=[REDACTED]
    # - token=value -> token=[REDACTED]
    # - secret=value -> secret=[REDACTED]
    # - password=value -> password=[REDACTED]
    # - signed URLs with query params containing signature/key/token
    # - Host absolute paths like /source/file.mp4 -> [HOST_PATH_REDACTED]
    # - BUT keep container paths like /videos/file.mp4 for debugging
```

**Security checklist:**
- ✅ Never expose actual API keys
- ✅ Never expose environment variables
- ✅ Never expose credentials
- ✅ Never expose signed URLs
- ✅ Truncate excessively long lines (e.g., max 2000 chars per line)

---

## TASK 4: Create AI_RULES.md

### Goal
Document rules for future AI modifications

### Implementation Details

**Location:** `/root/media-handler/ffmpeg-api/AI_RULES.md`

**Content structure:**

```markdown
# AI Rules for FFmpeg API

## Core Principles

### 1. Internal-Only Service
- This API is internal-only and must remain internal-only
- Called by MovieShaker internal systems only
- Never add public-facing features
- Never assume open internet access
- Never add CORS middleware for public domains

### 2. Authentication
- All `/api/*` endpoints MUST require X-Internal-API-Key authentication
- Use `Depends(verify_api_key)` in route decorator
- Only exception: `/health` endpoint (no auth required)
- Never bypass authentication
- Never add authentication to /health

### 3. No Frontend Changes
- This repository contains backend API only
- Do not modify any frontend code
- Do not create frontend files
- Frontend is managed separately

### 4. No Infrastructure Changes
- Do not add databases
- Do not add message queues (Redis, RabbitMQ, etc.)
- Do not add background job schedulers (Celery, etc.)
- Do not add new containers
- Do not run multiple services in one container
- Keep the single-service architecture

### 5. Docker Execution Security
- Always use argument arrays for subprocess calls
- NEVER use shell=True
- NEVER pass user input directly to subprocess
- Always validate and sanitize inputs
- Command building example: ["docker", "run", "--rm", "-v", f"{path}:/videos", "media-handler"] + command_args

### 6. Input Validation
- Validate all request parameters
- Never trust user input
- Check file existence before processing
- Validate file paths (prevent directory traversal)
- Sanitize all strings before logging

### 7. Code Quality
- Keep code minimal and readable
- Avoid over-engineering
- Avoid unnecessary abstractions
- Use Python standard library when possible
- Only add external dependencies if truly necessary
- Document why new dependencies are needed

### 8. Logging
- Log to /tmp/ffmpeg-api.log only
- Never log sensitive data:
  - API keys
  - Environment variables
  - Credentials
  - Signed URLs
- Truncate stderr to prevent log flooding (8KB max)
- Use standard library logging

### 9. Error Handling
- Return consistent error responses: {"status": "error", "message": "..."}
- Never expose internal paths in error messages
- Never expose stack traces to API responses
- Log detailed errors to log file, return sanitized errors to client

### 10. Dependencies
- Current: FastAPI, Uvicorn, Pydantic
- Before adding new dependencies:
  - Check if standard library can do it
  - Justify the addition
  - Consider security implications
  - Update requirements.txt with pinned versions

### 11. Docker Environment
- API runs in Docker container
- Has access to Docker socket for FFmpeg worker execution
- File storage: /source (mounted volume)
- Temp storage: /tmp
- Never modify Dockerfile without explicit instruction

### 12. Backward Compatibility
- Do not change existing endpoint behavior
- Do not modify request/response schemas of existing endpoints
- Maintain response format: SuccessResponse | ErrorResponse
- New features must be additive only

## Forbidden Actions
- ❌ Expose API to public internet
- ❌ Remove or bypass authentication
- ❌ Add database
- ❌ Add message queue
- ❌ Use shell=True in subprocess
- ❌ Log sensitive data
- ❌ Add frontend code
- ❌ Create multiple services
- ❌ Break existing endpoint contracts
- ❌ Add complex abstractions without justification

## Allowed Actions
- ✅ Add new authenticated endpoints
- ✅ Add input validation
- ✅ Improve error handling
- ✅ Add operational logging
- ✅ Refactor for clarity (keeping same behavior)
- ✅ Fix security issues
- ✅ Optimize performance
- ✅ Add documentation

## Review Checklist
Before making changes, verify:
- [ ] All endpoints have authentication (except /health)
- [ ] No shell injection vulnerabilities
- [ ] No sensitive data in logs
- [ ] No breaking changes to existing endpoints
- [ ] Code is minimal and readable
- [ ] No new infrastructure components
- [ ] Docker execution uses argument arrays
- [ ] Input validation is present
- [ ] Error messages don't expose internals
```

**File placement:** Root of ffmpeg-api directory (same level as Dockerfile)

---

## Implementation Order

### Phase 1: Logging Infrastructure
1. Create `app/logger.py` with sanitization functions
2. Integrate logging into `docker_exec.py`
3. Test log file creation and writing

### Phase 2: /api/instructions Endpoint
1. Add response schemas to `schemas.py`
2. Implement endpoint in `main.py`
3. Document all 9 FFmpeg endpoints
4. Test with valid API key

### Phase 3: /api/logs Endpoint
1. Add log reading functions to `logger.py`
2. Add response schema to `schemas.py`
3. Implement endpoint in `main.py`
4. Test line limits and sanitization

### Phase 4: Documentation
1. Create `AI_RULES.md` with all rules
2. Verify all rules are comprehensive

---

## Testing Strategy

### Manual Testing
1. **Logging:**
   - Execute each FFmpeg endpoint
   - Verify `/tmp/ffmpeg-api.log` is created
   - Verify log format is correct
   - Verify no sensitive data in logs

2. **GET /api/instructions:**
   - Request without API key → 401
   - Request with invalid API key → 401
   - Request with valid API key → 200 with full documentation
   - Verify all 10 endpoints documented (9 FFmpeg + /health)

3. **GET /api/logs:**
   - Request without API key → 401
   - Request with valid API key, default lines → 200 with up to 200 lines
   - Request with `?lines=50` → 200 with up to 50 lines
   - Request with `?lines=2000` → 200 with max 1000 lines (capped)
   - Verify sensitive data is redacted
   - Request when log file doesn't exist → 200 with empty logs array

### Edge Cases
- Empty log file
- Log file doesn't exist
- Requesting more lines than file contains
- Log file with sensitive data (verify redaction)
- Concurrent writes to log file

---

## Files to Create/Modify

### New Files (2)
1. `/root/media-handler/ffmpeg-api/app/logger.py` - Logging utilities
2. `/root/media-handler/ffmpeg-api/AI_RULES.md` - AI modification rules

### Modified Files (3)
1. `/root/media-handler/ffmpeg-api/app/main.py`
   - Add GET /api/instructions endpoint
   - Add GET /api/logs endpoint
   - Import new schemas
   - **NO logging calls added here** (all logging in docker_exec.py)

2. `/root/media-handler/ffmpeg-api/app/schemas.py`
   - Add `EndpointInfo` model
   - Add `InstructionsResponse` model
   - Add `LogsResponse` model

3. `/root/media-handler/ffmpeg-api/app/docker_exec.py`
   - Import logger functions
   - Add logging calls at key points in `execute_ffmpeg_command()`

### No Changes Required
- `app/auth.py` - Authentication already implemented correctly
- `app/ffmpeg.py` - Command builders don't need modification
- `app/__init__.py` - Empty init file
- `Dockerfile` - No container changes needed
- `requirements.txt` - No new dependencies needed

---

## Security Considerations

### Authentication
- Both new endpoints require X-Internal-API-Key
- Reuse existing `verify_api_key` dependency

### Log Sanitization
- Must redact:
  - API key values
  - Environment variable dumps
  - Credentials (key=, token=, secret=, password=)
  - Signed URLs with query parameters
  - Any PII if present

### File System
- Log file: `/tmp/ffmpeg-api.log` (ephemeral, container-scoped)
- Never log to mounted volumes
- No log rotation needed (container is ephemeral)

### Denial of Service
- Cap log lines at 1000
- Truncate stderr at 8KB
- Truncate individual log lines at 2000 chars
- No unbounded resource consumption

---

## Acceptance Criteria

### ✅ Feature Complete When:
1. **Logging:**
   - [ ] `/tmp/ffmpeg-api.log` created on first request
   - [ ] All FFmpeg operations logged
   - [ ] No sensitive data in logs
   - [ ] Timestamps in ISO 8601 format with UTC

2. **GET /api/instructions:**
   - [ ] Requires authentication
   - [ ] Returns JSON with all 10 endpoints documented (9 FFmpeg + /health)
   - [ ] Each endpoint has: name, method, path, description, request_body, success_response, error_response
   - [ ] Response matches specified schema
   - [ ] Uses Field(default_factory=...) for dict defaults (no Pydantic linting issues)

3. **GET /api/logs:**
   - [ ] Requires authentication
   - [ ] Returns last N lines (default 200, max 1000)
   - [ ] Handles missing log file gracefully
   - [ ] Sanitizes sensitive data
   - [ ] Accepts `?lines=N` query parameter

4. **AI_RULES.md:**
   - [ ] File exists at `/root/media-handler/ffmpeg-api/AI_RULES.md`
   - [ ] Contains all 12 core principles
   - [ ] Contains forbidden/allowed actions
   - [ ] Contains review checklist
   - [ ] No secrets or credentials in file

5. **No Breaking Changes:**
   - [ ] All existing endpoints still work
   - [ ] No changes to request/response schemas of existing endpoints
   - [ ] No new dependencies added
   - [ ] No frontend modifications
   - [ ] No infrastructure changes

---

## Rollback Plan

### If Issues Occur:
1. **Logging failures:** Check file permissions on `/tmp`
2. **New endpoints don't work:** Verify schemas imported correctly
3. **Authentication fails:** Verify `Depends(verify_api_key)` applied
4. **Performance issues:** Check log file size, implement rotation if needed

### Rollback steps:
1. Remove new endpoints from `main.py`
2. Remove logging calls from `docker_exec.py`
3. Delete `app/logger.py`
4. Remove new schemas from `schemas.py`
5. Restart service

---

## Estimated Effort

- **Logging infrastructure:** 1-2 hours
- **/api/instructions endpoint:** 1 hour
- **/api/logs endpoint:** 1-2 hours
- **AI_RULES.md:** 30 minutes
- **Testing:** 1 hour
- **Total:** 4.5-6.5 hours

---

## Notes

- Keep implementation minimal (per requirements)
- Use Python standard library only (no new dependencies)
- All code must be readable and self-documenting
- Follow existing code style (FastAPI patterns, Pydantic models)
- No complex abstractions or frameworks

---

## Next Steps After Approval

1. Review this plan with team
2. Get approval for implementation approach
3. Execute Phase 1 (Logging)
4. Execute Phase 2 (/api/instructions)
5. Execute Phase 3 (/api/logs)
6. Execute Phase 4 (AI_RULES.md)
7. Perform manual testing
8. Deploy to development environment
9. Monitor logs for issues
10. Deploy to production

---

**Plan Status:** Ready for Review  
**Created:** 2026-01-10  
**Requires:** No new dependencies, no infrastructure changes  
**Risk Level:** Low (additive changes only, no breaking modifications)
