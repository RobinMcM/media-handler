#!/usr/bin/env python3
"""
Test script for POST /api/ffmpeg/mux.
Tests local-file mode: sends one video and one audio. With no output_destination the API
streams the result; the script saves it to --output. Optional --presigned-put-url returns JSON.
Usage:
  export INTERNAL_API_KEY=your_key
  python scripts/test_mux.py --video clip.mp4 --audio music.mp3 --output out.mp4  # stream, save to out.mp4
  python scripts/test_mux.py --video clip.mp4 --audio music.mp3 --presigned-put-url "https://..."  # upload, JSON response
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser(description="Test POST /api/ffmpeg/mux (local mode)")
    ap.add_argument("--base-url", default=os.getenv("FFMPEG_API_URL", "http://localhost:8000"), help="API base URL")
    ap.add_argument("--api-key", default=os.getenv("INTERNAL_API_KEY"), help="X-Internal-API-Key")
    ap.add_argument("--video", required=True, help="Video filename (under SOURCE_DIR) or path")
    ap.add_argument("--audio", required=True, help="Audio filename (under SOURCE_DIR) or path")
    ap.add_argument("--output", help="Save streamed output to this path (use when not providing presigned URL)")
    ap.add_argument("--presigned-put-url", help="If set, upload result here and expect JSON response")
    args = ap.parse_args()

    if not args.api_key:
        print("Error: Set INTERNAL_API_KEY or pass --api-key", file=sys.stderr)
        sys.exit(1)
    if not args.output and not args.presigned_put_url:
        print("Error: Provide --output (to save stream) or --presigned-put-url", file=sys.stderr)
        sys.exit(1)
    if args.output and args.presigned_put_url:
        print("Error: Use either --output or --presigned-put-url, not both", file=sys.stderr)
        sys.exit(1)

    try:
        import httpx
    except ImportError:
        print("Error: httpx required. pip install httpx", file=sys.stderr)
        sys.exit(1)

    url = f"{args.base_url.rstrip('/')}/api/ffmpeg/mux"
    payload = {"video": args.video, "audio": args.audio}
    if args.presigned_put_url:
        payload["output_destination"] = {"presigned_put_url": args.presigned_put_url}
    headers = {"X-Internal-API-Key": args.api_key}

    print(f"POST {url}")
    print(f"Body: {payload}")
    r = httpx.post(url, json=payload, headers=headers, timeout=600.0)

    if r.status_code != 200:
        try:
            data = r.json()
        except Exception:
            data = r.text
        print(f"HTTP {r.status_code}: {data}", file=sys.stderr)
        sys.exit(1)

    if args.presigned_put_url:
        data = r.json()
        if data.get("status") == "error":
            print(f"API error: {data.get('message', data)}", file=sys.stderr)
            sys.exit(1)
        if data.get("status") != "ok":
            print(f"Unexpected response: {data}", file=sys.stderr)
            sys.exit(1)
        print(f"OK: {data.get('output', 'uploaded')}")
    else:
        with open(args.output, "wb") as f:
            f.write(r.content)
        print(f"OK: streamed output saved to {args.output}")
    sys.exit(0)


if __name__ == "__main__":
    main()
