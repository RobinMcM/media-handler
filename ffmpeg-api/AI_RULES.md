# AI Rules for FFmpeg API

This document defines rules for AI-assisted modifications to this codebase. These rules are non-negotiable and must be followed to maintain security, reliability, and architectural integrity.

---

## Core Principles

### 1. Internal-Only Service

- This API is **internal-only** and must remain internal-only
- Called by MovieShaker internal systems only
- **Never** add public-facing features
- **Never** assume open internet access
- **Never** add CORS middleware for public domains
- All endpoints serve internal infrastructure only

### 2. Authentication

- All `/api/*` endpoints **MUST** require `X-Internal-API-Key` authentication
- Use `Depends(verify_api_key)` in route decorator
- **Only exception:** `/health` endpoint (no auth required for monitoring)
- **Never** bypass authentication on protected endpoints
- **Never** add authentication to `/health`
- API keys must be loaded from `INTERNAL_API_KEYS` environment variable

### 3. No Frontend Changes

- This repository contains **backend API only**
- **Do not** modify any frontend code
- **Do not** create frontend files (HTML, CSS, JavaScript for browsers)
- Frontend is managed separately in a different repository
- Focus exclusively on API functionality

### 4. No Infrastructure Changes

- **Do not** add databases (PostgreSQL, MySQL, SQLite, etc.)
- **Do not** add message queues (Redis, RabbitMQ, Kafka, etc.)
- **Do not** add background job schedulers (Celery, APScheduler, etc.)
- **Do not** add new containers to docker-compose
- **Do not** run multiple services in one container
- Keep the single-service architecture
- The API wraps an existing FFmpeg Docker worker—that's the only infrastructure

### 5. Docker Execution Security

- **Always** use argument arrays for subprocess calls
- **NEVER** use `shell=True` in subprocess execution
- **NEVER** pass user input directly to subprocess without validation
- Always validate and sanitize inputs before building commands
- **Correct pattern:**
  ```python
  subprocess.run(["docker", "run", "--rm", "-v", f"{path}:/videos", "media-handler"] + command_args)
  ```
- **Forbidden pattern:**
  ```python
  subprocess.run(f"docker run -v {path}:/videos media-handler {user_input}", shell=True)
  ```

### 6. Input Validation

- **Validate all request parameters** before processing
- **Never trust user input**
- Check file existence before processing
- Validate file paths to prevent directory traversal attacks
- Sanitize all strings before logging
- Use Pydantic models for automatic validation
- Reject requests with invalid or missing required fields

### 7. Code Quality

- Keep code **minimal and readable**
- Avoid over-engineering and unnecessary abstractions
- Use Python standard library when possible
- Only add external dependencies if truly necessary
- Document **why** new dependencies are needed
- Follow existing code patterns and style
- Prefer clarity over cleverness

### 8. Logging

- Log to `/tmp/ffmpeg-api.log` only
- Use Python's standard `logging` module
- **Never log sensitive data:**
  - API keys or authentication tokens
  - Environment variables
  - Credentials (passwords, secrets)
  - Signed URLs or pre-signed S3 URLs
- Truncate stderr to prevent log flooding (8KB max per error)
- Sanitize logs before writing
- Redact host absolute paths but preserve container paths for debugging
- Example safe log: `docker run --rm -v [HOST_PATH_REDACTED]:/videos media-handler concat a.mp4 b.mp4 out.mp4`

### 9. Error Handling

- Return consistent error responses: `{"status": "error", "message": "..."}`
- **Never expose internal paths** in error messages sent to clients
- **Never expose stack traces** to API responses
- Log detailed errors to log file for debugging
- Return sanitized, user-friendly errors to clients
- Handle all exceptions gracefully
- Include timeout handling for long-running operations

### 10. Dependencies

- **Current dependencies:** FastAPI, Uvicorn, Pydantic
- Before adding new dependencies:
  - Check if Python standard library can provide the functionality
  - Justify the addition with a clear use case
  - Consider security implications and maintenance burden
  - Update `requirements.txt` with **pinned versions** (e.g., `fastapi==0.109.0`)
- Avoid adding heavy frameworks for simple tasks

### 11. Docker Environment

- API runs in a Docker container
- Has access to Docker socket for FFmpeg worker execution
- File storage paths:
  - `/source` - mounted volume for media files
  - `/tmp` - temporary storage for job directories
- **Never modify Dockerfile** without explicit instruction
- **Never change volume mounts** without explicit instruction
- Respect the existing container architecture

### 12. Backward Compatibility

- **Do not** change existing endpoint behavior
- **Do not** modify request/response schemas of existing endpoints
- Maintain response format: `SuccessResponse | ErrorResponse`
- New features must be **additive only**
- Existing clients must continue to work without changes
- If breaking changes are absolutely necessary, they must be explicitly requested and documented

---

## Forbidden Actions

The following actions are **strictly prohibited** unless explicitly requested:

- ❌ Expose API to public internet
- ❌ Remove or bypass authentication on protected endpoints
- ❌ Add database (SQL, NoSQL, or otherwise)
- ❌ Add message queue or pub/sub system
- ❌ Use `shell=True` in subprocess calls
- ❌ Log sensitive data (keys, tokens, credentials, secrets)
- ❌ Add frontend code to this repository
- ❌ Create multiple services in one container
- ❌ Break existing endpoint contracts or response formats
- ❌ Add complex abstractions without clear justification
- ❌ Change existing FFmpeg command behavior
- ❌ Modify docker-compose or add containers
- ❌ Skip input validation
- ❌ Expose internal implementation details in API responses

---

## Allowed Actions

The following actions are permitted and encouraged when they improve the service:

- ✅ Add new authenticated endpoints (with `Depends(verify_api_key)`)
- ✅ Add or improve input validation
- ✅ Improve error handling and error messages
- ✅ Add operational logging (with proper sanitization)
- ✅ Refactor for clarity while keeping same behavior
- ✅ Fix security vulnerabilities
- ✅ Optimize performance without changing functionality
- ✅ Add documentation (code comments, docstrings, API docs)
- ✅ Add request/response examples
- ✅ Improve type hints and Pydantic models
- ✅ Add health checks and monitoring endpoints

---

## Security Requirements

### Authentication
- All API endpoints under `/api/*` must verify `X-Internal-API-Key`
- Use existing `verify_api_key` dependency
- Return 401 for missing or invalid keys

### Input Sanitization
- Validate all file paths
- Prevent directory traversal (e.g., `../../etc/passwd`)
- Reject suspicious patterns in filenames
- Validate numeric inputs are within acceptable ranges

### Log Sanitization
Logs must **never** include:
- API key values
- Environment variable dumps
- Credentials (password=, secret=, token=, key=)
- Signed URLs with query parameters
- Personally Identifiable Information (PII)

If these appear in logs, they must be redacted:
- `X-Internal-API-Key: abc123` → `X-Internal-API-Key: [REDACTED]`
- `key=secret123` → `key=[REDACTED]`
- `/source/sensitive/path.mp4` → `[HOST_PATH_REDACTED]`

### DoS Prevention
- Cap log line requests at 1000 maximum
- Truncate stderr at 8KB per error
- Truncate individual log lines at 2KB
- Implement timeouts on subprocess calls (currently 1 hour)
- No unbounded resource consumption

---

## Code Patterns

### Correct: Subprocess with Argument Array
```python
command = ["docker", "run", "--rm", "-v", f"{job_dir}:/videos", "media-handler"]
command.extend(["concat", input1, input2, output])
result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
```

### Incorrect: Subprocess with Shell String
```python
# NEVER DO THIS
command = f"docker run -v {job_dir}:/videos media-handler concat {input1} {input2} {output}"
result = subprocess.run(command, shell=True)  # FORBIDDEN
```

### Correct: Input Validation
```python
from pydantic import BaseModel, validator

class TrimRequest(BaseModel):
    input: str
    output: str
    start: Optional[float] = None
    
    @validator('input', 'output')
    def validate_filename(cls, v):
        if '..' in v or v.startswith('/'):
            raise ValueError('Invalid filename')
        return v
```

### Correct: Error Response
```python
try:
    result = process_video(request)
    return SuccessResponse(output=result)
except FileNotFoundError:
    # Log detailed error internally
    logger.error(f"File not found: {request.input}")
    # Return sanitized error to client
    return ErrorResponse(message="Input file not found")
```

---

## Review Checklist

Before making changes, verify:

- [ ] All endpoints have authentication (except `/health`)
- [ ] No shell injection vulnerabilities (`shell=True` not used)
- [ ] No sensitive data in logs (keys, secrets, tokens redacted)
- [ ] No breaking changes to existing endpoints
- [ ] Code is minimal and readable
- [ ] No new infrastructure components (DB, queue, etc.)
- [ ] Docker execution uses argument arrays
- [ ] Input validation is present and thorough
- [ ] Error messages don't expose internal paths or stack traces
- [ ] New dependencies are justified and pinned to versions
- [ ] Existing tests still pass (if tests exist)
- [ ] Documentation is updated if needed

---

## Testing Requirements

When adding or modifying endpoints:

1. **Authentication:** Verify 401 response for missing/invalid API key
2. **Input validation:** Test with invalid inputs (empty, malformed, malicious)
3. **Error handling:** Test failure cases (missing files, timeouts, etc.)
4. **Logging:** Verify logs contain expected information without sensitive data
5. **Response format:** Ensure response matches schema (SuccessResponse | ErrorResponse)

---

## Deployment Notes

- API runs in Docker container with access to Docker socket
- Environment variables required:
  - `INTERNAL_API_KEYS` - comma-separated list of valid API keys
  - `SOURCE_DIR` - path to media files directory (default: `/source`)
- Port: 8000 (internal only, not exposed to internet)
- Health check: `GET /health` (no auth required)
- Logs: `/tmp/ffmpeg-api.log` (ephemeral, container-scoped)

---

## Common Mistakes to Avoid

1. **Adding logging to `main.py` with fake job IDs**
   - ❌ Wrong: `log_request(endpoint, "pre-execution")`
   - ✅ Correct: Log only in `docker_exec.py` where real job ID exists

2. **Over-sanitizing logs to the point of uselessness**
   - ❌ Wrong: Redact all paths including container paths
   - ✅ Correct: Redact host paths, keep container paths for debugging

3. **Using mutable defaults in Pydantic models**
   - ❌ Wrong: `auth: dict = {"header": "X-Internal-API-Key"}`
   - ✅ Correct: `auth: Dict[str, str] = Field(default_factory=lambda: {"header": "X-Internal-API-Key"})`

4. **Breaking existing endpoint behavior**
   - ❌ Wrong: Changing response format of `/api/ffmpeg/concat`
   - ✅ Correct: Add new endpoints or optional parameters

5. **Exposing sensitive data in error messages**
   - ❌ Wrong: `return {"error": f"Failed to process {full_path}"}`
   - ✅ Correct: `return {"error": "Failed to process input file"}`

---

## When in Doubt

- **Prefer simplicity** over complexity
- **Prefer security** over convenience
- **Prefer explicit** over implicit
- **Ask for clarification** rather than making assumptions
- **Review these rules** before making significant changes

---

## Maintenance

- Review these rules quarterly
- Update when new patterns emerge
- Document exceptions when they occur
- Keep aligned with MovieShaker security policies

---

**Last Updated:** 2026-01-10  
**Version:** 1.0  
**Status:** Active
