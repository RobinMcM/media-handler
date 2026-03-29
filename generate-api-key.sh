#!/bin/bash
set -euo pipefail

COUNT=1
ENV_FILE=""
APPEND_EXISTING=false

show_help() {
    cat <<'EOF'
Generate secure API key(s) for media-handler (INTERNAL_API_KEYS).

Usage:
  ./generate-api-key.sh [options]

Options:
  --count N             Number of new keys to generate (default: 1)
  --env-file PATH       Update INTERNAL_API_KEYS in this .env file
  --append-existing     When used with --env-file, append new keys to existing keys
  -h, --help            Show this help message

Examples:
  # Generate one key and print it
  ./generate-api-key.sh

  # Generate two keys and print INTERNAL_API_KEYS=... line
  ./generate-api-key.sh --count 2

  # Rotate keys in .env (replace existing INTERNAL_API_KEYS)
  ./generate-api-key.sh --env-file .env

  # Rolling rotation: keep old keys and append one new key
  ./generate-api-key.sh --env-file .env --append-existing
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --count)
            COUNT="${2:-}"
            shift 2
            ;;
        --env-file)
            ENV_FILE="${2:-}"
            shift 2
            ;;
        --append-existing)
            APPEND_EXISTING=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Use --help for usage."
            exit 1
            ;;
    esac
done

if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -lt 1 ]]; then
    echo "--count must be a positive integer" >&2
    exit 1
fi

NEW_KEYS="$(python3 - "$COUNT" <<'PY'
import secrets
import sys

count = int(sys.argv[1])
keys = []
for _ in range(count):
    # 32 random bytes, URL-safe token; prefix helps identify service scope.
    keys.append("mh_" + secrets.token_urlsafe(32))
print(",".join(keys))
PY
)"

echo "Generated key(s):"
IFS=',' read -r -a KEY_ARR <<< "$NEW_KEYS"
for key in "${KEY_ARR[@]}"; do
    echo "  $key"
done
echo ""
echo "Env format:"
echo "INTERNAL_API_KEYS=$NEW_KEYS"

if [[ -n "$ENV_FILE" ]]; then
    if [[ ! -f "$ENV_FILE" ]]; then
        echo ""
        echo "Env file not found: $ENV_FILE" >&2
        exit 1
    fi

    BACKUP_PATH="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$ENV_FILE" "$BACKUP_PATH"

    python3 - "$ENV_FILE" "$NEW_KEYS" "$APPEND_EXISTING" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
new_keys = sys.argv[2]
append_existing = sys.argv[3].lower() == "true"

content = env_path.read_text(encoding="utf-8")
lines = content.splitlines()

found = False
updated_lines = []

for line in lines:
    if line.startswith("INTERNAL_API_KEYS="):
        found = True
        if append_existing:
            existing = line.split("=", 1)[1].strip()
            if existing:
                merged = f"{existing},{new_keys}"
            else:
                merged = new_keys
            updated_lines.append(f"INTERNAL_API_KEYS={merged}")
        else:
            updated_lines.append(f"INTERNAL_API_KEYS={new_keys}")
    else:
        updated_lines.append(line)

if not found:
    updated_lines.append(f"INTERNAL_API_KEYS={new_keys}")

env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
PY

    echo ""
    echo "Updated: $ENV_FILE"
    echo "Backup:  $BACKUP_PATH"
    echo ""
    echo "Next step: restart ffmpeg-api so it picks up the new key(s)."
fi
