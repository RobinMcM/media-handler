"""
Valkey-backed admission control for FFmpeg API.

Provides:
- Global concurrency semaphore (limit max concurrent FFmpeg jobs)
- Per-API-key rate limiting
- Job deduplication (prevent duplicate concurrent requests)

If Valkey is unavailable, FAIL OPEN (allow requests but log warnings).
"""

import os
import hashlib
import logging
from typing import Optional, Tuple
from datetime import datetime

# Lazy import redis to avoid hard dependency
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


logger = logging.getLogger("ffmpeg-api")


# Configuration from environment
VALKEY_URL = os.getenv("VALKEY_URL", "redis://valkey:6379")
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# Key prefixes
PREFIX_SEMAPHORE = "ffmpeg:semaphore:jobs"
PREFIX_JOB = "ffmpeg:job"
PREFIX_RATE_LIMIT = "rl"
PREFIX_DEDUPE = "dedupe"

# TTLs (seconds)
TTL_JOB_WATCHDOG = 3600  # 1 hour max job runtime
TTL_DEDUPE = 300  # 5 minutes for deduplication
TTL_RATE_LIMIT = 60  # 1 minute for rate limit window


class ValkeyGuard:
    """Valkey-backed admission control."""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._available = False
        self._init_client()
    
    def _init_client(self):
        """Initialize Redis client. Fail open if unavailable."""
        if not REDIS_AVAILABLE:
            logger.warning("redis library not installed, admission control disabled (fail open)")
            return
        
        try:
            self._client = redis.from_url(
                VALKEY_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            self._client.ping()
            self._available = True
            logger.info(f"Valkey connected at {VALKEY_URL}")
        except Exception as e:
            logger.warning(f"Valkey unavailable, admission control disabled (fail open): {e}")
            self._client = None
            self._available = False
    
    def is_available(self) -> bool:
        """Check if Valkey is available."""
        return self._available and self._client is not None
    
    def _fingerprint_api_key(self, api_key: str) -> str:
        """
        Create a short fingerprint of API key for privacy.
        Never store full keys in Valkey.
        """
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    def check_rate_limit(self, api_key: str) -> Tuple[bool, str]:
        """
        Check if API key has exceeded rate limit.
        
        Returns:
            (allowed: bool, error_message: str)
        """
        if not self.is_available():
            # Fail open
            return True, ""
        
        try:
            fingerprint = self._fingerprint_api_key(api_key)
            # Use minute-level bucket: YYYYMMDDHHMM
            minute_bucket = datetime.utcnow().strftime("%Y%m%d%H%M")
            key = f"{PREFIX_RATE_LIMIT}:{fingerprint}:{minute_bucket}"
            
            # Increment counter
            count = self._client.incr(key)
            
            # Set expiry on first request
            if count == 1:
                self._client.expire(key, TTL_RATE_LIMIT)
            
            if count > RATE_LIMIT_PER_MINUTE:
                return False, f"Rate limit exceeded ({RATE_LIMIT_PER_MINUTE} requests per minute)"
            
            return True, ""
        
        except Exception as e:
            logger.warning(f"Rate limit check failed (fail open): {e}")
            return True, ""
    
    def acquire_slot(self, job_id: str) -> Tuple[bool, str]:
        """
        Acquire a global concurrency slot.
        
        Uses a Redis set to track active job IDs.
        Adds TTL watchdog for crash recovery.
        
        Returns:
            (acquired: bool, error_message: str)
        """
        if not self.is_available():
            # Fail open
            return True, ""
        
        try:
            # Clean up expired jobs first
            self._cleanup_expired_jobs()
            
            # Check current size
            current_size = self._client.scard(PREFIX_SEMAPHORE)
            
            if current_size >= MAX_CONCURRENT_JOBS:
                return False, f"Server busy, please retry (max {MAX_CONCURRENT_JOBS} concurrent jobs)"
            
            # Add job to set
            added = self._client.sadd(PREFIX_SEMAPHORE, job_id)
            
            if not added:
                # Job ID already in set (shouldn't happen with UUIDs)
                logger.warning(f"Job {job_id} already in semaphore set")
                return True, ""
            
            # Set watchdog TTL for this job
            watchdog_key = f"{PREFIX_JOB}:{job_id}"
            self._client.setex(watchdog_key, TTL_JOB_WATCHDOG, "active")
            
            logger.info(f"Acquired slot for job {job_id} ({current_size + 1}/{MAX_CONCURRENT_JOBS})")
            return True, ""
        
        except Exception as e:
            logger.warning(f"Slot acquisition failed (fail open): {e}")
            return True, ""
    
    def release_slot(self, job_id: str):
        """Release a global concurrency slot."""
        if not self.is_available():
            return
        
        try:
            # Remove from set
            removed = self._client.srem(PREFIX_SEMAPHORE, job_id)
            
            # Remove watchdog
            watchdog_key = f"{PREFIX_JOB}:{job_id}"
            self._client.delete(watchdog_key)
            
            if removed:
                current_size = self._client.scard(PREFIX_SEMAPHORE)
                logger.info(f"Released slot for job {job_id} ({current_size}/{MAX_CONCURRENT_JOBS})")
        
        except Exception as e:
            logger.warning(f"Slot release failed: {e}")
    
    def _cleanup_expired_jobs(self):
        """Remove jobs from semaphore set if their watchdog has expired."""
        try:
            # Get all job IDs in semaphore
            job_ids = self._client.smembers(PREFIX_SEMAPHORE)
            
            for job_id in job_ids:
                watchdog_key = f"{PREFIX_JOB}:{job_id}"
                # Check if watchdog exists
                if not self._client.exists(watchdog_key):
                    # Watchdog expired, remove from set
                    self._client.srem(PREFIX_SEMAPHORE, job_id)
                    logger.warning(f"Cleaned up expired job {job_id} from semaphore")
        
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
    
    def acquire_dedupe(self, dedupe_key: str) -> Tuple[bool, str]:
        """
        Acquire a deduplication lock.
        
        Uses SETNX to atomically check and set.
        
        Returns:
            (acquired: bool, error_message: str)
        """
        if not self.is_available():
            # Fail open (no deduplication)
            return True, ""
        
        try:
            key = f"{PREFIX_DEDUPE}:{dedupe_key}"
            
            # SETNX: set if not exists
            acquired = self._client.set(key, "locked", nx=True, ex=TTL_DEDUPE)
            
            if not acquired:
                return False, "Duplicate job in progress"
            
            logger.info(f"Acquired dedupe lock: {dedupe_key[:16]}...")
            return True, ""
        
        except Exception as e:
            logger.warning(f"Dedupe acquisition failed (fail open): {e}")
            return True, ""
    
    def release_dedupe(self, dedupe_key: str):
        """Release a deduplication lock."""
        if not self.is_available():
            return
        
        try:
            key = f"{PREFIX_DEDUPE}:{dedupe_key}"
            deleted = self._client.delete(key)
            
            if deleted:
                logger.info(f"Released dedupe lock: {dedupe_key[:16]}...")
        
        except Exception as e:
            logger.warning(f"Dedupe release failed: {e}")


# Global singleton instance
_guard_instance: Optional[ValkeyGuard] = None


def get_guard() -> ValkeyGuard:
    """Get or create the global ValkeyGuard instance."""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = ValkeyGuard()
    return _guard_instance
