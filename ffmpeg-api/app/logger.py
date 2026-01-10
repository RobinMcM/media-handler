import logging
import re
from pathlib import Path
from typing import List
from collections import deque

# Configuration
LOG_FILE = "/tmp/ffmpeg-api.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_STDERR_HEAD = 2048  # First N chars to capture (FFmpeg initialization)
MAX_STDERR_TAIL = 8192  # Last N chars to capture (where FFmpeg errors usually appear)
MAX_LOG_LINE_LENGTH = 2000

# Configure logger
logger = logging.getLogger("ffmpeg-api")
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler(LOG_FILE, mode='a')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
formatter.converter = lambda *args: __import__('time').gmtime(*args)  # Use UTC
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def sanitize_command(command: List[str]) -> str:
    """
    Sanitize docker command for logging.
    - Redact host absolute paths
    - Preserve container paths (/videos/...)
    - Keep mount structure visible for debugging
    """
    sanitized = []
    
    for i, arg in enumerate(command):
        # Handle volume mounts: -v /host/path:/container/path
        if arg == "-v" and i + 1 < len(command):
            mount_spec = command[i + 1]
            if ":" in mount_spec:
                # Split mount into host:container
                parts = mount_spec.split(":", 1)
                sanitized.append("-v")
                sanitized.append(f"[HOST_PATH_REDACTED]:{parts[1]}")
                continue
        elif i > 0 and command[i - 1] == "-v":
            # Already handled in previous iteration
            continue
        
        # Redact any remaining host absolute paths (but keep container paths)
        if arg.startswith("/tmp/job-") or arg.startswith("/source/"):
            # This is a host path, redact the directory but keep the structure visible
            sanitized.append("[HOST_PATH_REDACTED]")
        else:
            sanitized.append(arg)
    
    return " ".join(sanitized)


def sanitize_stderr(text: str) -> str:
    """
    Remove sensitive data from stderr/error text.
    - Redact API keys, tokens, secrets, passwords
    - Redact signed URLs
    - Redact host absolute paths (but keep container paths)
    Does NOT truncate - that's handled separately by format_stderr
    """
    # Redact API keys
    text = re.sub(r'(X-Internal-API-Key:\s*)[^\s]+', r'\1[REDACTED]', text, flags=re.IGNORECASE)
    
    # Redact key=value, token=value, secret=value, password=value patterns
    text = re.sub(r'\b(key|token|secret|password|apikey|api_key)=([^\s&]+)', r'\1=[REDACTED]', text, flags=re.IGNORECASE)
    
    # Redact signed URLs (query params with signature/key/token)
    text = re.sub(r'\?(.*?)(signature|key|token|sig)=([^&\s]+)', r'?[SIGNED_URL_REDACTED]', text, flags=re.IGNORECASE)
    
    # Redact host paths but keep container paths
    text = re.sub(r'/tmp/job-[a-f0-9\-]+', '[HOST_JOB_DIR]', text)
    text = re.sub(r'/source/[^\s]+', '[HOST_SOURCE_PATH]', text)
    
    return text


def sanitize_log_line(line: str) -> str:
    """
    Remove sensitive data from a single log line.
    Used for /api/logs endpoint only.
    """
    # Redact API keys
    line = re.sub(r'(X-Internal-API-Key:\s*)[^\s]+', r'\1[REDACTED]', line, flags=re.IGNORECASE)
    
    # Redact key=value, token=value, secret=value, password=value patterns
    line = re.sub(r'\b(key|token|secret|password|apikey|api_key)=([^\s&]+)', r'\1=[REDACTED]', line, flags=re.IGNORECASE)
    
    # Redact signed URLs (query params with signature/key/token)
    line = re.sub(r'\?(.*?)(signature|key|token|sig)=([^&\s]+)', r'?[SIGNED_URL_REDACTED]', line, flags=re.IGNORECASE)
    
    # Redact host paths but keep container paths
    line = re.sub(r'/tmp/job-[a-f0-9\-]+', '[HOST_JOB_DIR]', line)
    line = re.sub(r'/source/[^\s]+', '[HOST_SOURCE_PATH]', line)
    
    return line


def format_stderr(stderr: str) -> str:
    """
    Format stderr for logging: sanitize first, then slice to head+tail if needed.
    FFmpeg errors often appear at the very end, so we capture:
    - First 2048 chars (initialization/setup info)
    - Last 8192 chars (actual error messages)
    
    Args:
        stderr: Raw stderr string from FFmpeg
        
    Returns:
        Sanitized and formatted string with head and tail sections
    """
    if not stderr:
        return ""
    
    # STEP 1: Sanitize the full stderr FIRST (before slicing)
    stderr = sanitize_stderr(stderr)
    
    total_length = len(stderr)
    
    # STEP 2: If short enough, return full sanitized content
    if total_length <= (MAX_STDERR_HEAD + MAX_STDERR_TAIL):
        return stderr
    
    # STEP 3: Extract head and tail from sanitized content
    stderr_head = stderr[:MAX_STDERR_HEAD]
    stderr_tail = stderr[-MAX_STDERR_TAIL:]
    
    # Calculate how many chars were omitted
    omitted = total_length - MAX_STDERR_HEAD - MAX_STDERR_TAIL
    
    # Format with clear section markers
    return (
        f"[STDERR_HEAD]\n"
        f"{stderr_head}\n\n"
        f"[... {omitted} characters omitted ...]\n\n"
        f"[STDERR_TAIL]\n"
        f"{stderr_tail}"
    )


def log_request(endpoint: str, job_id: str):
    """Log incoming request"""
    logger.info(f"job={job_id} endpoint={endpoint} status=started")


def log_docker_command(job_id: str, command: List[str]):
    """Log docker command execution (sanitized)"""
    sanitized_cmd = sanitize_command(command)
    # Also log array representation for debugging argument parsing
    cmd_repr = repr([arg if not arg.startswith('/') else '[PATH]' for arg in command])
    logger.info(f"job={job_id} command={sanitized_cmd}")
    logger.info(f"job={job_id} command_array={cmd_repr}")


def log_success(job_id: str, output_file: str):
    """Log successful completion"""
    logger.info(f"job={job_id} status=success output={output_file}")


def log_error(job_id: str, error_message: str):
    """Log error with sanitization and head+tail formatting"""
    # Format stderr: sanitize first, then head+tail if needed
    error_message = format_stderr(error_message)
    
    logger.error(f"job={job_id} status=error message={error_message}")


def read_last_n_lines(filepath: str, n: int) -> List[str]:
    """
    Read last N lines from log file efficiently.
    Returns empty list if file doesn't exist.
    """
    path = Path(filepath)
    
    if not path.exists():
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            # Use deque with maxlen for efficient tail reading
            return list(deque(f, maxlen=n))
    except Exception as e:
        logger.error(f"Failed to read log file: {e}")
        return []


def get_sanitized_logs(n: int = 200) -> List[str]:
    """
    Get last N lines from log file with sanitization.
    Removes sensitive data before returning.
    """
    lines = read_last_n_lines(LOG_FILE, n)
    
    # Sanitize each line
    sanitized_lines = []
    for line in lines:
        sanitized = sanitize_log_line(line.rstrip('\n'))
        sanitized_lines.append(sanitized)
    
    return sanitized_lines
