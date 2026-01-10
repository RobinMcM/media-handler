# POST /api/ffmpeg/concat_spaces Implementation

**Date:** 2026-01-10  
**Status:** ✅ Complete  
**Feature:** Concatenate videos from DigitalOcean Spaces

---

## Overview

Implemented new endpoint `POST /api/ffmpeg/concat_spaces` that enables video concatenation from DigitalOcean Spaces without requiring files to exist locally or be uploaded from MovieShaker.

**Flow:**
1. Downloads two input videos from DO Spaces to temp directory
2. Runs existing local concat pipeline (Docker FFmpeg worker)
3. Uploads stitched output back to DO Spaces
4. Returns output key and optional public URL

---

## Files Created

### 1. `/root/media-handler/ffmpeg-api/app/spaces.py` (125 lines)

**Purpose:** Minimal S3/Spaces client wrapper using boto3

**Functions:**
- `download_key_to_path(spaces_key, local_path)` - Download from Spaces
- `upload_path_to_key(local_path, spaces_key, content_type)` - Upload to Spaces
- `get_public_url(spaces_key)` - Generate public URL if configured

**Configuration (from env vars):**
- `SPACES_BUCKET` - Required
- `SPACES_ENDPOINT` - Required (e.g., `https://lon1.digitaloceanspaces.com`)
- `SPACES_ACCESS_KEY_ID` - Required
- `SPACES_SECRET_ACCESS_KEY` - Required
- `SPACES_PUBLIC_BASE_URL` - Optional (for generating public URLs)

**Security:**
- ✅ Does not log credentials
- ✅ Raises clear errors for missing configuration
- ✅ Handles S3 client errors gracefully

---

## Files Modified

### 1. `/root/media-handler/ffmpeg-api/requirements.txt`

**Added:**
```
boto3==1.34.34
```

### 2. `/root/media-handler/ffmpeg-api/app/schemas.py`

**Added schemas:**

```python
class SpacesObjectRef(BaseModel):
    spaces_key: str

class ConcatSpacesRequest(BaseModel):
    inputs: List[SpacesObjectRef]
    output: SpacesObjectRef

class ConcatSpacesResponse(BaseModel):
    status: str = "ok"
    output_key: str
    output_url: Optional[str]
```

### 3. `/root/media-handler/ffmpeg-api/app/main.py`

**Added:**
- New endpoint `POST /api/ffmpeg/concat_spaces`
- Updated `/api/instructions` to document the new endpoint

---

## API Contract

### Endpoint
```
POST /api/ffmpeg/concat_spaces
```

### Headers
```
X-Internal-API-Key: <secret>
Content-Type: application/json
```

### Request Body
```json
{
  "inputs": [
    { "spaces_key": "path/to/input1.mp4" },
    { "spaces_key": "path/to/input2.mp4" }
  ],
  "output": { "spaces_key": "path/to/output.mp4" }
}
```

### Success Response
```json
{
  "status": "ok",
  "output_key": "path/to/output.mp4",
  "output_url": "https://bucket.lon1.digitaloceanspaces.com/path/to/output.mp4"
}
```

**Note:** `output_url` is `null` if `SPACES_PUBLIC_BASE_URL` is not configured.

### Error Response
```json
{
  "status": "error",
  "message": "Error description"
}
```

---

## Validation Rules

### Input Validation
1. **Exactly 2 inputs required**
   - Request with 0, 1, or 3+ inputs → 422 validation error

2. **spaces_key must be non-empty**
   - Empty or whitespace-only keys → error

3. **No directory traversal**
   - Keys containing `..` → error
   - Keys starting with `/` → error

4. **Video file extensions only**
   - Allowed: `.mp4`, `.mov`, `.m4v`, `.webm` (case-insensitive)
   - Other extensions → error

### Example Invalid Requests

**Wrong number of inputs:**
```json
{
  "inputs": [{"spaces_key": "video.mp4"}],
  "output": {"spaces_key": "out.mp4"}
}
```
→ Error: "Exactly 2 inputs required for concat_spaces"

**Directory traversal attempt:**
```json
{
  "inputs": [
    {"spaces_key": "../../../etc/passwd"},
    {"spaces_key": "video2.mp4"}
  ],
  "output": {"spaces_key": "out.mp4"}
}
```
→ Error: "Invalid spaces_key: cannot contain '..' or start with '/'"

**Invalid file extension:**
```json
{
  "inputs": [
    {"spaces_key": "video1.avi"},
    {"spaces_key": "video2.mp4"}
  ],
  "output": {"spaces_key": "out.mp4"}
}
```
→ Error: "Invalid input file extension: .avi. Allowed: .mp4, .mov, .m4v, .webm"

---

## Implementation Details

### Job Lifecycle

1. **Generate job ID** - UUID for tracking
2. **Create temp directory** - `/tmp/job-<uuid>/`
3. **Download inputs** - From Spaces to `a.mp4`, `b.mp4`
4. **Run Docker FFmpeg** - Existing concat worker
5. **Upload output** - To Spaces at requested key
6. **Cleanup** - Always delete temp directory (finally block)
7. **Return response** - With output key and URL

### Logging

Uses existing `app/logger.py`:
- ✅ Logs job_id for tracking
- ✅ Logs sanitized Docker command
- ✅ Logs success/error status
- ✅ Redacts credentials and sensitive paths
- ✅ Logs to `/tmp/ffmpeg-api.log`

**Example log entries:**
```
2026-01-10T12:00:00Z INFO job=abc123 endpoint=concat_spaces status=started
2026-01-10T12:00:01Z INFO job=abc123 command=docker run --rm -v [HOST_PATH_REDACTED]:/videos media-handler concat a.mp4 b.mp4 output.mp4
2026-01-10T12:00:10Z INFO job=abc123 status=success output=path/to/output.mp4
```

### Error Handling

**Configuration errors:**
- Missing env vars → 500 error with clear message
- Invalid Spaces credentials → error during download/upload

**Download errors:**
- Object not found → "Object not found in Spaces: <key>"
- Permission denied → "Failed to download from Spaces: <code>"
- Network issues → boto3 exception message

**FFmpeg errors:**
- Docker execution fails → "FFmpeg concat failed: <stderr>"
- Output file missing → error message

**Upload errors:**
- Upload fails → "Failed to upload output to Spaces: <code>"

---

## Environment Variables Required

Add these to the FFmpeg API container:

```bash
SPACES_BUCKET=my-bucket-name
SPACES_ENDPOINT=https://lon1.digitaloceanspaces.com
SPACES_ACCESS_KEY_ID=DO_SPACES_KEY
SPACES_SECRET_ACCESS_KEY=DO_SPACES_SECRET

# Optional - for generating public URLs
SPACES_PUBLIC_BASE_URL=https://my-bucket.lon1.digitaloceanspaces.com
```

**Security notes:**
- ✅ Never commit these to version control
- ✅ Not logged anywhere in code
- ✅ Loaded at runtime from environment

---

## Testing

### 1. Verify Endpoint Exists

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "$FFMPEG_API_URL/api/ffmpeg/concat_spaces" \
  -H "X-Internal-API-Key: $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected:** `422` (validation error, not `404`)

### 2. Test with Invalid Data

```bash
# Wrong number of inputs
curl -X POST "$FFMPEG_API_URL/api/ffmpeg/concat_spaces" \
  -H "X-Internal-API-Key: $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs":[{"spaces_key":"video1.mp4"}],
    "output":{"spaces_key":"out.mp4"}
  }'
```

**Expected:** Error response with "Exactly 2 inputs required"

### 3. Test with Real Spaces Keys

```bash
curl -X POST "$FFMPEG_API_URL/api/ffmpeg/concat_spaces" \
  -H "X-Internal-API-Key: $INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs":[
      {"spaces_key":"videos/input1.mp4"},
      {"spaces_key":"videos/input2.mp4"}
    ],
    "output":{"spaces_key":"videos/output.mp4"}
  }'
```

**Expected:** Success response with output_key and output_url

### 4. Verify Upload in Spaces

Check DigitalOcean Spaces console or use AWS CLI:

```bash
aws s3 ls s3://my-bucket/videos/ \
  --endpoint-url=https://lon1.digitaloceanspaces.com
```

Should see `output.mp4` in the listing.

### 5. Test Authentication

```bash
# No API key
curl -X POST "$FFMPEG_API_URL/api/ffmpeg/concat_spaces" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**Expected:** `401 Unauthorized`

---

## Security Checklist ✅

- ✅ **Authentication required** - Uses `Depends(verify_api_key)`
- ✅ **Input validation** - Rejects path traversal, invalid extensions
- ✅ **No shell injection** - Uses argument arrays, not `shell=True`
- ✅ **Credentials not logged** - Spaces keys/secrets never in logs
- ✅ **Temp directory cleanup** - Always removed in finally block
- ✅ **Error messages sanitized** - No internal paths exposed
- ✅ **Logging redacts sensitive data** - Uses existing sanitization

---

## Performance Considerations

### File Transfer Times
- Downloads 2 videos from Spaces (depends on file size and network)
- FFmpeg processing (depends on video length and complexity)
- Upload 1 video to Spaces

**Typical flow for 1-minute 1080p videos:**
- Download: ~5-10 seconds (2 files)
- Concat: ~5-10 seconds
- Upload: ~3-5 seconds
- **Total: ~15-25 seconds**

### Timeout
- Docker subprocess timeout: 3600 seconds (1 hour)
- Sufficient for most video processing tasks
- Adjust if processing very large files

### Cleanup
- Temp directory always deleted in `finally` block
- Prevents disk space issues from failed jobs

---

## Limitations

1. **Exactly 2 inputs only**
   - Current implementation: 2 inputs hardcoded
   - Future enhancement: support N inputs

2. **Video files only**
   - Allowed extensions: `.mp4`, `.mov`, `.m4v`, `.webm`
   - Audio-only files not supported in this endpoint

3. **No progress feedback**
   - Synchronous operation, client waits for completion
   - Future enhancement: async processing with job status endpoint

4. **Single bucket**
   - All operations use bucket from `SPACES_BUCKET` env var
   - Cannot mix buckets in single request

---

## Comparison with Local Concat

### POST /api/ffmpeg/concat (existing)
- **Input:** Local files in `/source` directory
- **Output:** Local file in `/source` directory
- **Use case:** Files already on same host

### POST /api/ffmpeg/concat_spaces (new)
- **Input:** Files in DigitalOcean Spaces
- **Output:** File in DigitalOcean Spaces
- **Use case:** MovieShaker on different host, files in cloud storage

**Both:**
- ✅ Use same FFmpeg Docker worker
- ✅ Same concat logic and quality
- ✅ Require authentication
- ✅ Return consistent response format

---

## Integration with MovieShaker

### Before (without concat_spaces)
1. MovieShaker uploads videos to Spaces
2. MovieShaker downloads videos from Spaces
3. MovieShaker uploads videos to FFmpeg API
4. FFmpeg API processes locally
5. FFmpeg API returns result to MovieShaker
6. MovieShaker uploads result to Spaces

**Problem:** Double transfer of large video files

### After (with concat_spaces)
1. MovieShaker uploads videos to Spaces
2. MovieShaker calls `/api/ffmpeg/concat_spaces` with Spaces keys
3. FFmpeg API downloads from Spaces (fast DigitalOcean internal network)
4. FFmpeg API processes locally
5. FFmpeg API uploads result to Spaces (fast internal network)
6. FFmpeg API returns Spaces key/URL to MovieShaker

**Benefit:** No video transfer between MovieShaker and FFmpeg API

---

## Future Enhancements (Not Implemented)

1. **Support N inputs** - Currently limited to 2
2. **Async processing** - Return job ID, poll for status
3. **Multiple buckets** - Support cross-bucket operations
4. **More operations** - trim_spaces, scale_spaces, etc.
5. **Progress webhooks** - Notify when processing complete
6. **Signed URLs** - Generate temporary download URLs

---

## Rollback Plan

If issues occur:

1. **Remove endpoint** - Comment out route in `main.py`
2. **Remove from instructions** - Remove from `/api/instructions` list
3. **Keep dependencies** - boto3 can stay (harmless if unused)
4. **Restart service**

**No breaking changes** - Existing endpoints unaffected

---

## Documentation Updates

### /api/instructions now includes:

```json
{
  "name": "concat_spaces",
  "method": "POST",
  "path": "/api/ffmpeg/concat_spaces",
  "description": "Concatenate two videos from DigitalOcean Spaces",
  "request_body": {
    "inputs": [
      {"spaces_key": "path/to/input1.mp4"},
      {"spaces_key": "path/to/input2.mp4"}
    ],
    "output": {"spaces_key": "path/to/output.mp4"}
  },
  "success_response": {
    "status": "ok",
    "output_key": "path/to/output.mp4",
    "output_url": "https://bucket.region.digitaloceanspaces.com/path/to/output.mp4"
  },
  "error_response": {
    "status": "error",
    "message": "Error description"
  }
}
```

---

## Compliance with AI_RULES.md ✅

Verified against all 12 core principles:

1. ✅ **Internal-only** - Requires API key authentication
2. ✅ **Authentication** - Uses `Depends(verify_api_key)`
3. ✅ **No frontend changes** - Backend only
4. ✅ **No infrastructure** - No DB, queue, or new containers
5. ✅ **Docker security** - Argument arrays, no `shell=True`
6. ✅ **Input validation** - Validates keys, extensions, paths
7. ✅ **Code quality** - Minimal, readable, standard library where possible
8. ✅ **Logging** - Uses existing logger, sanitizes sensitive data
9. ✅ **Error handling** - Consistent error responses
10. ✅ **Dependencies** - boto3 pinned, justified (S3/Spaces client)
11. ✅ **Docker environment** - Works in existing container
12. ✅ **Backward compatibility** - No changes to existing endpoints

---

## Success Criteria - All Met ✅

1. ✅ New endpoint `POST /api/ffmpeg/concat_spaces` implemented
2. ✅ Downloads from DigitalOcean Spaces
3. ✅ Runs existing concat pipeline
4. ✅ Uploads to DigitalOcean Spaces
5. ✅ Returns output key and optional public URL
6. ✅ Requires authentication
7. ✅ Input validation (2 inputs, valid extensions, no traversal)
8. ✅ Proper error handling
9. ✅ Logging with sanitization
10. ✅ Cleanup in finally block
11. ✅ Updated `/api/instructions`
12. ✅ No linting errors
13. ✅ No breaking changes
14. ✅ Follows AI_RULES.md

---

**Implementation Status:** ✅ Complete and Ready for Testing  
**Linting Status:** ✅ No errors  
**Breaking Changes:** ❌ None  
**New Dependency:** boto3==1.34.34  
**Risk Level:** 🟢 Low (additive feature, isolated code)
