#!/bin/sh
set -e

# Validate argument count
if [ "$#" -ne 3 ]; then
  echo "Error: Expected exactly 3 arguments (input1 input2 output)" >&2
  exit 1
fi

INPUT1="/videos/$1"
INPUT2="/videos/$2"
OUTPUT="/videos/$3"

# Validate input files exist
if [ ! -f "$INPUT1" ]; then
  echo "Error: Input file not found: $INPUT1" >&2
  exit 1
fi

if [ ! -f "$INPUT2" ]; then
  echo "Error: Input file not found: $INPUT2" >&2
  exit 1
fi

# Run FFmpeg concat
ffmpeg -y \
  -i "$INPUT1" \
  -i "$INPUT2" \
  -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" \
  "$OUTPUT"
