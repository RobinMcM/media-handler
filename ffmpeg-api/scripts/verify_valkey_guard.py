#!/usr/bin/env python3
"""
Verification script for Valkey admission control.

Tests:
1. Valkey connectivity
2. Global concurrency semaphore (MAX_CONCURRENT_JOBS)
3. Rate limiting
4. Job deduplication

Run from ffmpeg-api container or with proper environment.
"""

import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.valkey_guard import get_guard, MAX_CONCURRENT_JOBS, RATE_LIMIT_PER_MINUTE


def test_connectivity():
    """Test 1: Valkey connectivity"""
    print("=" * 60)
    print("TEST 1: Valkey Connectivity")
    print("=" * 60)
    
    guard = get_guard()
    
    if guard.is_available():
        print("✓ Valkey is available and connected")
        print(f"  URL: {os.getenv('VALKEY_URL', 'redis://valkey:6379')}")
        return True
    else:
        print("✗ Valkey is NOT available (fail-open mode)")
        print("  This is expected if Valkey is not running")
        return False


def test_semaphore():
    """Test 2: Global concurrency semaphore"""
    print("\n" + "=" * 60)
    print("TEST 2: Global Concurrency Semaphore")
    print("=" * 60)
    print(f"MAX_CONCURRENT_JOBS: {MAX_CONCURRENT_JOBS}")
    
    guard = get_guard()
    
    if not guard.is_available():
        print("⊘ Skipping (Valkey not available)")
        return True
    
    # Acquire MAX_CONCURRENT_JOBS slots
    job_ids = []
    for i in range(MAX_CONCURRENT_JOBS):
        job_id = f"test-job-{i}"
        acquired, msg = guard.acquire_slot(job_id)
        if acquired:
            print(f"  ✓ Acquired slot {i+1}/{MAX_CONCURRENT_JOBS} (job={job_id})")
            job_ids.append(job_id)
        else:
            print(f"  ✗ Failed to acquire slot {i+1}: {msg}")
            return False
    
    # Try to acquire one more (should fail)
    extra_job_id = f"test-job-extra"
    acquired, msg = guard.acquire_slot(extra_job_id)
    if not acquired:
        print(f"  ✓ Correctly blocked extra slot: {msg}")
    else:
        print(f"  ✗ Should have blocked extra slot but didn't!")
        job_ids.append(extra_job_id)
        return False
    
    # Release all slots
    for job_id in job_ids:
        guard.release_slot(job_id)
        print(f"  ✓ Released slot (job={job_id})")
    
    # Verify can acquire again after release
    test_job_id = "test-job-after-release"
    acquired, msg = guard.acquire_slot(test_job_id)
    if acquired:
        print(f"  ✓ Can acquire slot after release (job={test_job_id})")
        guard.release_slot(test_job_id)
        return True
    else:
        print(f"  ✗ Failed to acquire slot after release: {msg}")
        return False


def test_rate_limiting():
    """Test 3: Rate limiting"""
    print("\n" + "=" * 60)
    print("TEST 3: Rate Limiting")
    print("=" * 60)
    print(f"RATE_LIMIT_PER_MINUTE: {RATE_LIMIT_PER_MINUTE}")
    
    guard = get_guard()
    
    if not guard.is_available():
        print("⊘ Skipping (Valkey not available)")
        return True
    
    test_api_key = "test-api-key-for-rate-limit"
    
    # Make RATE_LIMIT_PER_MINUTE requests
    print(f"  Making {RATE_LIMIT_PER_MINUTE} requests...")
    for i in range(RATE_LIMIT_PER_MINUTE):
        allowed, msg = guard.check_rate_limit(test_api_key)
        if not allowed:
            print(f"  ✗ Request {i+1} was blocked but shouldn't be: {msg}")
            return False
    
    print(f"  ✓ First {RATE_LIMIT_PER_MINUTE} requests allowed")
    
    # Next request should be blocked
    allowed, msg = guard.check_rate_limit(test_api_key)
    if not allowed:
        print(f"  ✓ Request {RATE_LIMIT_PER_MINUTE + 1} correctly blocked: {msg}")
        return True
    else:
        print(f"  ✗ Request {RATE_LIMIT_PER_MINUTE + 1} should have been blocked!")
        return False


def test_deduplication():
    """Test 4: Job deduplication"""
    print("\n" + "=" * 60)
    print("TEST 4: Job Deduplication")
    print("=" * 60)
    
    guard = get_guard()
    
    if not guard.is_available():
        print("⊘ Skipping (Valkey not available)")
        return True
    
    dedupe_key = "test-dedupe-key-12345"
    
    # First acquisition should succeed
    acquired, msg = guard.acquire_dedupe(dedupe_key)
    if not acquired:
        print(f"  ✗ First dedupe acquisition failed: {msg}")
        return False
    print(f"  ✓ First acquisition succeeded (key={dedupe_key[:32]}...)")
    
    # Second acquisition should fail (duplicate)
    acquired, msg = guard.acquire_dedupe(dedupe_key)
    if acquired:
        print(f"  ✗ Second acquisition should have failed (duplicate) but didn't!")
        guard.release_dedupe(dedupe_key)  # Clean up
        return False
    print(f"  ✓ Second acquisition correctly blocked: {msg}")
    
    # Release lock
    guard.release_dedupe(dedupe_key)
    print(f"  ✓ Released dedupe lock")
    
    # Should be able to acquire again after release
    acquired, msg = guard.acquire_dedupe(dedupe_key)
    if not acquired:
        print(f"  ✗ Acquisition after release failed: {msg}")
        return False
    print(f"  ✓ Acquisition after release succeeded")
    
    # Clean up
    guard.release_dedupe(dedupe_key)
    
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("VALKEY ADMISSION CONTROL VERIFICATION")
    print("=" * 60)
    print()
    
    results = {
        "connectivity": test_connectivity(),
        "semaphore": test_semaphore(),
        "rate_limiting": test_rate_limiting(),
        "deduplication": test_deduplication()
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:20s}: {status}")
    
    print()
    
    all_passed = all(results.values())
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
