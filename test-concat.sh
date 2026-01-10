#!/bin/bash
# Test script for concat with audio detection

set -e

echo "=== Testing concat with audio detection ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

TEST_DIR="/tmp/concat-test-$$"
mkdir -p "$TEST_DIR"

cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

cd "$TEST_DIR"

echo "Creating test videos..."

# Create a silent video (no audio)
ffmpeg -f lavfi -i testsrc=duration=2:size=320x240:rate=30 \
    -pix_fmt yuv420p -y silent.mp4 >/dev/null 2>&1

# Create a video with audio
ffmpeg -f lavfi -i testsrc=duration=2:size=320x240:rate=30 \
    -f lavfi -i sine=frequency=1000:duration=2 \
    -pix_fmt yuv420p -y with-audio.mp4 >/dev/null 2>&1

echo "✓ Test videos created"
echo ""

# Test 1: Two silent videos
echo "Test 1: Concatenating two silent videos"
docker run --rm -v "$TEST_DIR:/videos" media-handler concat silent.mp4 silent.mp4 output1.mp4
if [ -f output1.mp4 ]; then
    echo -e "${GREEN}✓ Test 1 PASSED${NC} - Silent videos concatenated successfully"
else
    echo -e "${RED}✗ Test 1 FAILED${NC} - Output file not created"
    exit 1
fi
echo ""

# Test 2: Two videos with audio
echo "Test 2: Concatenating two videos with audio"
docker run --rm -v "$TEST_DIR:/videos" media-handler concat with-audio.mp4 with-audio.mp4 output2.mp4
if [ -f output2.mp4 ]; then
    echo -e "${GREEN}✓ Test 2 PASSED${NC} - Videos with audio concatenated successfully"
else
    echo -e "${RED}✗ Test 2 FAILED${NC} - Output file not created"
    exit 1
fi
echo ""

# Test 3: Mixed (one with audio, one without)
echo "Test 3: Concatenating mixed (audio + silent)"
docker run --rm -v "$TEST_DIR:/videos" media-handler concat with-audio.mp4 silent.mp4 output3.mp4
if [ -f output3.mp4 ]; then
    echo -e "${GREEN}✓ Test 3 PASSED${NC} - Mixed videos concatenated successfully (video-only)"
else
    echo -e "${RED}✗ Test 3 FAILED${NC} - Output file not created"
    exit 1
fi
echo ""

# Test 4: Missing output filename (should fail gracefully)
echo "Test 4: Testing missing output filename"
if docker run --rm -v "$TEST_DIR:/videos" media-handler concat silent.mp4 silent.mp4 "" 2>&1 | grep -q "output filename cannot be empty"; then
    echo -e "${GREEN}✓ Test 4 PASSED${NC} - Empty output filename rejected with clear error"
else
    echo -e "${RED}✗ Test 4 FAILED${NC} - Should have rejected empty output filename"
    exit 1
fi
echo ""

# Test 5: Output filename without extension (should fail gracefully)
echo "Test 5: Testing output without extension"
if docker run --rm -v "$TEST_DIR:/videos" media-handler concat silent.mp4 silent.mp4 "output" 2>&1 | grep -q "must have an extension"; then
    echo -e "${GREEN}✓ Test 5 PASSED${NC} - Output without extension rejected"
else
    echo -e "${RED}✗ Test 5 FAILED${NC} - Should have rejected filename without extension"
    exit 1
fi
echo ""

# Verify output files have correct properties
echo "Verifying output files..."

# Check output1 (silent) has no audio
AUDIO_COUNT=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 output1.mp4 | wc -l)
if [ "$AUDIO_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} output1.mp4 correctly has no audio stream"
else
    echo -e "${RED}✗${NC} output1.mp4 should not have audio stream"
    exit 1
fi

# Check output2 (with audio) has audio
AUDIO_COUNT=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 output2.mp4 | wc -l)
if [ "$AUDIO_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} output2.mp4 correctly has audio stream"
else
    echo -e "${RED}✗${NC} output2.mp4 should have audio stream"
    exit 1
fi

# Check output3 (mixed) has no audio (falls back to video-only)
AUDIO_COUNT=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 output3.mp4 | wc -l)
if [ "$AUDIO_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} output3.mp4 correctly has no audio stream (video-only concat)"
else
    echo -e "${RED}✗${NC} output3.mp4 should not have audio (video-only mode)"
    exit 1
fi

echo ""
echo -e "${GREEN}=== ALL TESTS PASSED ===${NC}"
echo ""
echo "Summary:"
echo "  ✓ Silent videos can be concatenated"
echo "  ✓ Videos with audio can be concatenated"
echo "  ✓ Mixed videos fall back to video-only concat"
echo "  ✓ Empty output filename is rejected"
echo "  ✓ Output without extension is rejected"
echo "  ✓ Output files have correct audio properties"
