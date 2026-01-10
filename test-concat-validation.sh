#!/bin/bash
# Comprehensive concat validation test - ensures output is non-empty and has valid duration

set -e

echo "=== Comprehensive Concat Validation Test ==="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

TEST_DIR="/tmp/concat-validation-test-$$"
mkdir -p "$TEST_DIR"

cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

cd "$TEST_DIR"

echo "Creating test videos..."

# Create video WITH audio (2 seconds, 30fps)
ffmpeg -f lavfi -i testsrc=duration=2:size=640x480:rate=30 \
    -f lavfi -i sine=frequency=1000:duration=2 \
    -pix_fmt yuv420p -y with-audio-1.mp4 >/dev/null 2>&1

ffmpeg -f lavfi -i testsrc=duration=2:size=640x480:rate=30 \
    -f lavfi -i sine=frequency=500:duration=2 \
    -pix_fmt yuv420p -y with-audio-2.mp4 >/dev/null 2>&1

# Create video WITHOUT audio (silent, 2 seconds, 30fps)
ffmpeg -f lavfi -i testsrc=duration=2:size=640x480:rate=30 \
    -pix_fmt yuv420p -y silent-1.mp4 >/dev/null 2>&1

ffmpeg -f lavfi -i testsrc=duration=2:size=640x480:rate=30 \
    -pix_fmt yuv420p -y silent-2.mp4 >/dev/null 2>&1

echo -e "${GREEN}✓${NC} Test videos created"
echo ""

# Helper function to validate output
validate_output() {
    local output_file=$1
    local test_name=$2
    local expected_min_duration=$3
    
    # Check file exists
    if [ ! -f "$output_file" ]; then
        echo -e "${RED}✗ FAILED${NC}: $test_name - output file not created"
        return 1
    fi
    
    # Check file size > 0
    local file_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null)
    if [ "$file_size" -eq 0 ]; then
        echo -e "${RED}✗ FAILED${NC}: $test_name - output file is empty (0 bytes)"
        return 1
    fi
    
    # Check duration > expected minimum
    local duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$output_file" 2>/dev/null)
    local duration_int=$(echo "$duration" | cut -d. -f1)
    
    if [ -z "$duration" ] || [ "$duration_int" -lt "$expected_min_duration" ]; then
        echo -e "${RED}✗ FAILED${NC}: $test_name - invalid duration (${duration}s, expected >= ${expected_min_duration}s)"
        return 1
    fi
    
    # Check has video stream
    local video_streams=$(ffprobe -v error -select_streams v -show_entries stream=codec_type -of csv=p=0 "$output_file" 2>/dev/null | wc -l)
    if [ "$video_streams" -eq 0 ]; then
        echo -e "${RED}✗ FAILED${NC}: $test_name - no video stream found"
        return 1
    fi
    
    echo -e "${GREEN}✓ PASSED${NC}: $test_name (${file_size} bytes, ${duration}s)"
    return 0
}

# Test 1: Two videos with audio
echo "Test 1: Concatenating two videos WITH audio"
if docker run --rm -v "$TEST_DIR:/videos" media-handler concat with-audio-1.mp4 with-audio-2.mp4 output-audio.mp4 2>&1 | tee test1.log; then
    validate_output "output-audio.mp4" "Test 1 (with audio)" 3
else
    echo -e "${RED}✗ FAILED${NC}: Test 1 - concat command failed"
    cat test1.log
    exit 1
fi
echo ""

# Test 2: Two videos WITHOUT audio
echo "Test 2: Concatenating two videos WITHOUT audio"
if docker run --rm -v "$TEST_DIR:/videos" media-handler concat silent-1.mp4 silent-2.mp4 output-silent.mp4 2>&1 | tee test2.log; then
    validate_output "output-silent.mp4" "Test 2 (no audio)" 3
else
    echo -e "${RED}✗ FAILED${NC}: Test 2 - concat command failed"
    cat test2.log
    exit 1
fi
echo ""

# Test 3: Mixed (one with audio, one without)
echo "Test 3: Concatenating MIXED (one with audio, one without)"
if docker run --rm -v "$TEST_DIR:/videos" media-handler concat with-audio-1.mp4 silent-1.mp4 output-mixed.mp4 2>&1 | tee test3.log; then
    validate_output "output-mixed.mp4" "Test 3 (mixed)" 3
else
    echo -e "${RED}✗ FAILED${NC}: Test 3 - concat command failed"
    cat test3.log
    exit 1
fi
echo ""

# Test 4: Verify audio presence in outputs
echo "Verifying audio streams..."

# output-audio.mp4 should have audio
audio_count=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 output-audio.mp4 2>/dev/null | wc -l)
if [ "$audio_count" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} output-audio.mp4 has audio stream"
else
    echo -e "${RED}✗${NC} output-audio.mp4 should have audio"
    exit 1
fi

# output-silent.mp4 should NOT have audio
audio_count=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 output-silent.mp4 2>/dev/null | wc -l)
if [ "$audio_count" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} output-silent.mp4 has no audio stream (correct)"
else
    echo -e "${YELLOW}⚠${NC} output-silent.mp4 has audio (unexpected but not critical)"
fi

# output-mixed.mp4 should NOT have audio (falls back to video-only)
audio_count=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 output-mixed.mp4 2>/dev/null | wc -l)
if [ "$audio_count" -eq 0 ]; then
    echo -e "${GREEN}✓${NC} output-mixed.mp4 has no audio stream (video-only mode)"
else
    echo -e "${YELLOW}⚠${NC} output-mixed.mp4 has audio (unexpected but not critical)"
fi

echo ""
echo -e "${GREEN}=== ALL VALIDATION TESTS PASSED ===${NC}"
echo ""
echo "Summary:"
echo "  ✓ Videos with audio: concatenated successfully with valid duration"
echo "  ✓ Videos without audio: concatenated successfully with valid duration"
echo "  ✓ Mixed videos: concatenated successfully (video-only mode)"
echo "  ✓ All output files have size > 0 bytes"
echo "  ✓ All output files have duration >= 3 seconds"
echo "  ✓ All output files have video streams"
