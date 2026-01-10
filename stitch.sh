#!/bin/sh
set -e

# Validate at least one argument
if [ "$#" -lt 1 ]; then
  echo "Error: No command specified" >&2
  echo "Usage: stitch <command> [options] <inputs> <output>" >&2
  exit 1
fi

COMMAND=$1
shift

# Command dispatcher
case "$COMMAND" in
  concat)
    # Validate arguments: need at least 3 (input1 input2 output)
    if [ "$#" -lt 3 ]; then
      echo "Error: concat requires at least 2 inputs and 1 output" >&2
      exit 1
    fi
    
    # Last argument is output
    OUTPUT="/videos/${!#}"
    
    # First pass: collect inputs and detect audio presence
    INPUTS=""
    INPUT_FILES=""
    COUNT=0
    HAS_AUDIO=1  # Assume audio exists until proven otherwise
    
    # Collect all input files
    while [ "$#" -gt 1 ]; do
      INPUT="/videos/$1"
      if [ ! -f "$INPUT" ]; then
        echo "Error: Input file not found: $INPUT" >&2
        exit 1
      fi
      INPUT_FILES="$INPUT_FILES $INPUT"
      INPUTS="$INPUTS -i $INPUT"
      COUNT=$((COUNT + 1))
      shift
    done
    
    # Check if all inputs have audio using ffprobe
    for INPUT in $INPUT_FILES; do
      AUDIO_STREAMS=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 "$INPUT" 2>/dev/null | wc -l)
      if [ "$AUDIO_STREAMS" -eq 0 ]; then
        echo "Detected input without audio: $INPUT (switching to video-only concat)"
        HAS_AUDIO=0
        break
      fi
    done
    
    # Build filter based on audio presence
    FILTER=""
    if [ "$HAS_AUDIO" -eq 1 ]; then
      # Both inputs have audio: concat audio and video
      IDX=0
      while [ "$IDX" -lt "$COUNT" ]; do
        FILTER="${FILTER}[$IDX:v][$IDX:a]"
        IDX=$((IDX + 1))
      done
      FILTER="${FILTER}concat=n=${COUNT}:v=1:a=1[v][a]"
      MAP_ARGS="-map [v] -map [a]"
    else
      # At least one input lacks audio: video-only concat
      IDX=0
      while [ "$IDX" -lt "$COUNT" ]; do
        FILTER="${FILTER}[$IDX:v]"
        IDX=$((IDX + 1))
      done
      FILTER="${FILTER}concat=n=${COUNT}:v=1:a=0[v]"
      MAP_ARGS="-map [v]"
    fi
    
    echo "Executing: ffmpeg -y $INPUTS -filter_complex \"$FILTER\" $MAP_ARGS $OUTPUT"
    ffmpeg -y $INPUTS -filter_complex "$FILTER" $MAP_ARGS "$OUTPUT"
    ;;
    
  trim)
    # Parse options: --start, --end, --duration
    START=""
    END=""
    DURATION=""
    
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --start)
          START="$2"
          shift 2
          ;;
        --end)
          END="$2"
          shift 2
          ;;
        --duration)
          DURATION="$2"
          shift 2
          ;;
        *)
          break
          ;;
      esac
    done
    
    # Validate remaining arguments (input output)
    if [ "$#" -ne 2 ]; then
      echo "Error: trim requires input and output files" >&2
      exit 1
    fi
    
    INPUT="/videos/$1"
    OUTPUT="/videos/$2"
    
    if [ ! -f "$INPUT" ]; then
      echo "Error: Input file not found: $INPUT" >&2
      exit 1
    fi
    
    # Build FFmpeg command
    OPTS=""
    if [ -n "$START" ]; then
      OPTS="$OPTS -ss $START"
    fi
    if [ -n "$END" ]; then
      OPTS="$OPTS -to $END"
    elif [ -n "$DURATION" ]; then
      OPTS="$OPTS -t $DURATION"
    fi
    
    echo "Executing: ffmpeg -y $OPTS -i $INPUT -c copy $OUTPUT"
    ffmpeg -y $OPTS -i "$INPUT" -c copy "$OUTPUT"
    ;;
    
  scale)
    # Parse options: --size (WxH), --aspect-ratio
    SIZE=""
    KEEP_ASPECT=0
    
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --size)
          SIZE="$2"
          shift 2
          ;;
        --aspect-ratio)
          KEEP_ASPECT=1
          shift
          ;;
        *)
          break
          ;;
      esac
    done
    
    if [ "$#" -ne 2 ]; then
      echo "Error: scale requires input and output files" >&2
      exit 1
    fi
    
    INPUT="/videos/$1"
    OUTPUT="/videos/$2"
    
    if [ ! -f "$INPUT" ]; then
      echo "Error: Input file not found: $INPUT" >&2
      exit 1
    fi
    
    if [ -z "$SIZE" ]; then
      echo "Error: --size is required" >&2
      exit 1
    fi
    
    # Parse WxH
    WIDTH=$(echo "$SIZE" | cut -d'x' -f1)
    HEIGHT=$(echo "$SIZE" | cut -d'x' -f2)
    
    if [ "$KEEP_ASPECT" -eq 1 ]; then
      HEIGHT="-1"
    fi
    
    FILTER="scale=${WIDTH}:${HEIGHT}"
    
    echo "Executing: ffmpeg -y -i $INPUT -vf \"$FILTER\" $OUTPUT"
    ffmpeg -y -i "$INPUT" -vf "$FILTER" "$OUTPUT"
    ;;
    
  crop)
    # Parse: x y width height input output
    if [ "$#" -ne 6 ]; then
      echo "Error: crop requires x y width height input output" >&2
      exit 1
    fi
    
    X="$1"
    Y="$2"
    WIDTH="$3"
    HEIGHT="$4"
    INPUT="/videos/$5"
    OUTPUT="/videos/$6"
    
    if [ ! -f "$INPUT" ]; then
      echo "Error: Input file not found: $INPUT" >&2
      exit 1
    fi
    
    FILTER="crop=${WIDTH}:${HEIGHT}:${X}:${Y}"
    
    echo "Executing: ffmpeg -y -i $INPUT -vf \"$FILTER\" $OUTPUT"
    ffmpeg -y -i "$INPUT" -vf "$FILTER" "$OUTPUT"
    ;;
    
  rotate)
    # Parse: angle input output
    if [ "$#" -ne 3 ]; then
      echo "Error: rotate requires angle input output" >&2
      exit 1
    fi
    
    ANGLE="$1"
    INPUT="/videos/$2"
    OUTPUT="/videos/$3"
    
    if [ ! -f "$INPUT" ]; then
      echo "Error: Input file not found: $INPUT" >&2
      exit 1
    fi
    
    # Map angles to transpose values
    case "$ANGLE" in
      90)
        FILTER="transpose=1"
        ;;
      180)
        FILTER="transpose=1,transpose=1"
        ;;
      270)
        FILTER="transpose=2"
        ;;
      *)
        echo "Error: Angle must be 90, 180, or 270" >&2
        exit 1
        ;;
    esac
    
    echo "Executing: ffmpeg -y -i $INPUT -vf \"$FILTER\" $OUTPUT"
    ffmpeg -y -i "$INPUT" -vf "$FILTER" "$OUTPUT"
    ;;
    
  mute)
    # Parse options: --normalize
    NORMALIZE=0
    
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --normalize)
          NORMALIZE=1
          shift
          ;;
        *)
          break
          ;;
      esac
    done
    
    if [ "$#" -ne 2 ]; then
      echo "Error: mute requires input and output files" >&2
      exit 1
    fi
    
    INPUT="/videos/$1"
    OUTPUT="/videos/$2"
    
    if [ ! -f "$INPUT" ]; then
      echo "Error: Input file not found: $INPUT" >&2
      exit 1
    fi
    
    if [ "$NORMALIZE" -eq 1 ]; then
      FILTER="loudnorm"
      echo "Executing: ffmpeg -y -i $INPUT -af \"$FILTER\" $OUTPUT"
      ffmpeg -y -i "$INPUT" -af "$FILTER" "$OUTPUT"
    else
      echo "Executing: ffmpeg -y -i $INPUT -an -c:v copy $OUTPUT"
      ffmpeg -y -i "$INPUT" -an -c:v copy "$OUTPUT"
    fi
    ;;
    
  overlay)
    # Parse options: --x, --y
    X="0"
    Y="0"
    
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --x)
          X="$2"
          shift 2
          ;;
        --y)
          Y="$2"
          shift 2
          ;;
        *)
          break
          ;;
      esac
    done
    
    if [ "$#" -ne 3 ]; then
      echo "Error: overlay requires base overlay output" >&2
      exit 1
    fi
    
    BASE="/videos/$1"
    OVER="/videos/$2"
    OUTPUT="/videos/$3"
    
    if [ ! -f "$BASE" ]; then
      echo "Error: Base file not found: $BASE" >&2
      exit 1
    fi
    
    if [ ! -f "$OVER" ]; then
      echo "Error: Overlay file not found: $OVER" >&2
      exit 1
    fi
    
    FILTER="overlay=${X}:${Y}"
    
    echo "Executing: ffmpeg -y -i $BASE -i $OVER -filter_complex \"$FILTER\" $OUTPUT"
    ffmpeg -y -i "$BASE" -i "$OVER" -filter_complex "$FILTER" "$OUTPUT"
    ;;
    
  watermark)
    # Parse options: --x, --y, --opacity, --position
    X=""
    Y=""
    OPACITY="1.0"
    POSITION=""
    
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --x)
          X="$2"
          shift 2
          ;;
        --y)
          Y="$2"
          shift 2
          ;;
        --opacity)
          OPACITY="$2"
          shift 2
          ;;
        --position)
          POSITION="$2"
          shift 2
          ;;
        *)
          break
          ;;
      esac
    done
    
    if [ "$#" -ne 3 ]; then
      echo "Error: watermark requires video image output" >&2
      exit 1
    fi
    
    VIDEO="/videos/$1"
    IMAGE="/videos/$2"
    OUTPUT="/videos/$3"
    
    if [ ! -f "$VIDEO" ]; then
      echo "Error: Video file not found: $VIDEO" >&2
      exit 1
    fi
    
    if [ ! -f "$IMAGE" ]; then
      echo "Error: Image file not found: $IMAGE" >&2
      exit 1
    fi
    
    # Position presets
    if [ -n "$POSITION" ]; then
      case "$POSITION" in
        top-left)
          X="10"
          Y="10"
          ;;
        top-right)
          X="W-w-10"
          Y="10"
          ;;
        bottom-left)
          X="10"
          Y="H-h-10"
          ;;
        bottom-right)
          X="W-w-10"
          Y="H-h-10"
          ;;
        center)
          X="(W-w)/2"
          Y="(H-h)/2"
          ;;
        *)
          echo "Error: Invalid position preset" >&2
          exit 1
          ;;
      esac
    fi
    
    # Default to top-left if no position specified
    if [ -z "$X" ]; then
      X="10"
      Y="10"
    fi
    
    # Build filter with opacity
    if [ "$OPACITY" != "1.0" ]; then
      FILTER="[1]format=rgba,colorchannelmixer=aa=${OPACITY}[logo];[0][logo]overlay=${X}:${Y}"
    else
      FILTER="overlay=${X}:${Y}"
    fi
    
    echo "Executing: ffmpeg -y -i $VIDEO -i $IMAGE -filter_complex \"$FILTER\" $OUTPUT"
    ffmpeg -y -i "$VIDEO" -i "$IMAGE" -filter_complex "$FILTER" "$OUTPUT"
    ;;
    
  format)
    # Parse options: --format, --vcodec, --acodec
    FORMAT=""
    VCODEC=""
    ACODEC=""
    
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --format)
          FORMAT="$2"
          shift 2
          ;;
        --vcodec)
          VCODEC="$2"
          shift 2
          ;;
        --acodec)
          ACODEC="$2"
          shift 2
          ;;
        *)
          break
          ;;
      esac
    done
    
    if [ "$#" -ne 2 ]; then
      echo "Error: format requires input and output files" >&2
      exit 1
    fi
    
    INPUT="/videos/$1"
    OUTPUT="/videos/$2"
    
    if [ ! -f "$INPUT" ]; then
      echo "Error: Input file not found: $INPUT" >&2
      exit 1
    fi
    
    OPTS=""
    if [ -n "$FORMAT" ]; then
      OPTS="$OPTS -f $FORMAT"
    fi
    if [ -n "$VCODEC" ]; then
      OPTS="$OPTS -c:v $VCODEC"
    fi
    if [ -n "$ACODEC" ]; then
      OPTS="$OPTS -c:a $ACODEC"
    fi
    
    echo "Executing: ffmpeg -y -i $INPUT $OPTS $OUTPUT"
    ffmpeg -y -i "$INPUT" $OPTS "$OUTPUT"
    ;;
    
  *)
    echo "Error: Unknown command: $COMMAND" >&2
    echo "Available commands: concat, trim, scale, crop, rotate, mute, overlay, watermark, format" >&2
    exit 1
    ;;
esac
