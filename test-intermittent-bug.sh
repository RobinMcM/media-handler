#!/bin/bash
# Test script to reproduce intermittent concat output filename bug

set -e

echo "=== Testing for intermittent concat output filename bug ==="
echo ""

TEST_DIR="/tmp/concat-intermittent-test-$$"
mkdir -p "$TEST_DIR"

cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

cd "$TEST_DIR"

# Create test videos
echo "Creating test videos..."
ffmpeg -f lavfi -i testsrc=duration=1:size=320x240:rate=30 \
    -pix_fmt yuv420p -y a.mp4 >/dev/null 2>&1

ffmpeg -f lavfi -i testsrc=duration=1:size=320x240:rate=30 \
    -pix_fmt yuv420p -y b.mp4 >/dev/null 2>&1

echo "✓ Test videos created"
echo ""

# Run the exact command 20 times to catch intermittent issues
FAILURES=0
SUCCESSES=0

echo "Running concat command 20 times to detect intermittent failures..."
echo ""

for i in $(seq 1 20); do
    echo -n "Run $i: "
    
    # Clean up previous output
    rm -f output.mp4
    
    # Run the exact docker command as logged
    if docker run --rm -v "$TEST_DIR:/videos" media-handler concat a.mp4 b.mp4 output.mp4 2>&1 | tee /tmp/concat-run-$i.log | grep -q "output filename cannot be empty"; then
        echo "FAILED (empty output error)"
        FAILURES=$((FAILURES + 1))
        echo "  Log saved to /tmp/concat-run-$i.log"
    elif [ -f output.mp4 ]; then
        echo "SUCCESS (output created)"
        SUCCESSES=$((SUCCESSES + 1))
    else
        echo "FAILED (no output file)"
        FAILURES=$((FAILURES + 1))
        echo "  Log saved to /tmp/concat-run-$i.log"
    fi
done

echo ""
echo "=== Results ==="
echo "Successes: $SUCCESSES / 20"
echo "Failures:  $FAILURES / 20"
echo ""

if [ "$FAILURES" -gt 0 ]; then
    echo "INTERMITTENT BUG DETECTED!"
    echo "Check logs in /tmp/concat-run-*.log for details"
    exit 1
else
    echo "All runs succeeded - bug may be fixed or not reproducible"
    exit 0
fi
