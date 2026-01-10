#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
CONTAINER_NAME="ffmpeg-api"
IMAGE_NAME="ffmpeg-api:latest"
PORT="8000"
MEDIA_DIR="/root/media-files"
ENV_FILE="/root/media-handler/.env"
DO_GIT_PULL=true

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

show_help() {
    cat << EOF
FFmpeg API Deployment Script

Usage: $0 [OPTIONS]

Options:
    --no-pull           Skip git pull (use local changes)
    --env-file PATH     Path to .env file (default: /root/media-handler/.env)
    --media-dir PATH    Path to media files directory (default: /root/media-files)
    --container NAME    Container name (default: ffmpeg-api)
    --port PORT         Port mapping (default: 8000)
    -h, --help          Show this help message

Environment Variables Required (in .env file):
    INTERNAL_API_KEYS           Comma-separated API keys
    SPACES_BUCKET               DigitalOcean Spaces bucket name
    SPACES_ENDPOINT             Spaces endpoint URL
    SPACES_ACCESS_KEY_ID        Spaces access key
    SPACES_SECRET_ACCESS_KEY    Spaces secret key
    SPACES_PUBLIC_BASE_URL      (Optional) Public base URL for Spaces

Examples:
    # Standard deployment
    ./deploy-ffmpeg-api.sh

    # Deploy without git pull
    ./deploy-ffmpeg-api.sh --no-pull

    # Use custom env file
    ./deploy-ffmpeg-api.sh --env-file /path/to/.env

    # Custom media directory
    ./deploy-ffmpeg-api.sh --media-dir /opt/media
EOF
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-pull)
            DO_GIT_PULL=false
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --media-dir)
            MEDIA_DIR="$2"
            shift 2
            ;;
        --container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Verify we're in the correct directory
cd "$SCRIPT_DIR"

print_header "FFmpeg API Deployment"
print_info "Container: $CONTAINER_NAME"
print_info "Image: $IMAGE_NAME"
print_info "Port: $PORT"
print_info "Media directory: $MEDIA_DIR"
print_info "Environment file: $ENV_FILE"
echo ""

# Step 1: Git Pull (optional)
if [ "$DO_GIT_PULL" = true ]; then
    print_header "Step 1: Pulling Latest Changes"
    
    if [ -d .git ]; then
        print_info "Pulling from git repository..."
        if git pull origin main 2>&1; then
            print_success "Git pull completed"
        else
            print_warning "Git pull failed or no changes (continuing anyway)"
        fi
    else
        print_warning "Not a git repository, skipping git pull"
    fi
else
    print_info "Skipping git pull (--no-pull flag set)"
fi

# Step 2: Verify environment file exists
print_header "Step 2: Checking Environment Configuration"

if [ ! -f "$ENV_FILE" ]; then
    print_error "Environment file not found: $ENV_FILE"
    echo ""
    print_info "Please create $ENV_FILE with the following variables:"
    echo "    INTERNAL_API_KEYS=your-key-1,your-key-2"
    echo "    SPACES_BUCKET=your-bucket"
    echo "    SPACES_ENDPOINT=https://lon1.digitaloceanspaces.com"
    echo "    SPACES_ACCESS_KEY_ID=your-key"
    echo "    SPACES_SECRET_ACCESS_KEY=your-secret"
    echo "    SPACES_PUBLIC_BASE_URL=https://your-bucket.lon1.digitaloceanspaces.com"
    exit 1
fi

print_success "Environment file found"

# Verify required environment variables
source "$ENV_FILE"
MISSING_VARS=()

if [ -z "$INTERNAL_API_KEYS" ]; then
    MISSING_VARS+=("INTERNAL_API_KEYS")
fi
if [ -z "$SPACES_BUCKET" ]; then
    MISSING_VARS+=("SPACES_BUCKET")
fi
if [ -z "$SPACES_ENDPOINT" ]; then
    MISSING_VARS+=("SPACES_ENDPOINT")
fi
if [ -z "$SPACES_ACCESS_KEY_ID" ]; then
    MISSING_VARS+=("SPACES_ACCESS_KEY_ID")
fi
if [ -z "$SPACES_SECRET_ACCESS_KEY" ]; then
    MISSING_VARS+=("SPACES_SECRET_ACCESS_KEY")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    print_error "Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "    - $var"
    done
    exit 1
fi

print_success "All required environment variables are set"

if [ -z "$SPACES_PUBLIC_BASE_URL" ]; then
    print_warning "SPACES_PUBLIC_BASE_URL not set (output_url will be null)"
fi

# Step 3: Stop and remove old container
print_header "Step 3: Stopping Old Container"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    print_info "Stopping container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME" || true
    
    print_info "Removing container: $CONTAINER_NAME"
    docker rm "$CONTAINER_NAME" || true
    
    print_success "Old container removed"
else
    print_info "No existing container found"
fi

# Step 4: Build new Docker image
print_header "Step 4: Building Docker Image"

print_info "Building image: $IMAGE_NAME"
print_info "Context: ffmpeg-api/"

if docker build -t "$IMAGE_NAME" -f ffmpeg-api/Dockerfile ffmpeg-api/; then
    print_success "Docker image built successfully"
else
    print_error "Docker build failed"
    exit 1
fi

# Step 5: Create media directory if it doesn't exist
print_header "Step 5: Preparing Media Directory"

if [ ! -d "$MEDIA_DIR" ]; then
    print_info "Creating media directory: $MEDIA_DIR"
    mkdir -p "$MEDIA_DIR"
    print_success "Media directory created"
else
    print_success "Media directory exists"
fi

# Step 6: Start new container
print_header "Step 6: Starting New Container"

print_info "Starting container: $CONTAINER_NAME"

docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "${PORT}:8000" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${MEDIA_DIR}:/source" \
    -v /tmp:/tmp \
    -e INTERNAL_API_KEYS="${INTERNAL_API_KEYS}" \
    -e SPACES_BUCKET="${SPACES_BUCKET}" \
    -e SPACES_ENDPOINT="${SPACES_ENDPOINT}" \
    -e SPACES_ACCESS_KEY_ID="${SPACES_ACCESS_KEY_ID}" \
    -e SPACES_SECRET_ACCESS_KEY="${SPACES_SECRET_ACCESS_KEY}" \
    -e SPACES_PUBLIC_BASE_URL="${SPACES_PUBLIC_BASE_URL:-}" \
    "$IMAGE_NAME"

print_success "Container started"

# Step 7: Wait for container to be ready
print_header "Step 7: Verifying Deployment"

print_info "Waiting for container to start..."
sleep 3

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    print_success "Container is running"
else
    print_error "Container failed to start"
    echo ""
    print_info "Showing container logs:"
    docker logs "$CONTAINER_NAME"
    exit 1
fi

# Test health endpoint
print_info "Testing health endpoint..."
sleep 2

if curl -s -f "http://localhost:${PORT}/health" > /dev/null 2>&1; then
    HEALTH_RESPONSE=$(curl -s "http://localhost:${PORT}/health")
    print_success "Health check passed: $HEALTH_RESPONSE"
else
    print_error "Health check failed"
    echo ""
    print_info "Showing container logs:"
    docker logs "$CONTAINER_NAME" 2>&1 | tail -20
    exit 1
fi

# Step 8: Show deployment summary
print_header "Deployment Complete"

echo -e "${GREEN}✓ FFmpeg API deployed successfully!${NC}\n"

print_info "Container Details:"
echo "    Name:       $CONTAINER_NAME"
echo "    Image:      $IMAGE_NAME"
echo "    Port:       $PORT"
echo "    Status:     $(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME")"
echo ""

print_info "Endpoints:"
echo "    Health:              http://localhost:${PORT}/health"
echo "    Instructions:        http://localhost:${PORT}/api/instructions"
echo "    Logs:                http://localhost:${PORT}/api/logs"
echo "    Concat (local):      http://localhost:${PORT}/api/ffmpeg/concat"
echo "    Concat (spaces):     http://localhost:${PORT}/api/ffmpeg/concat_spaces"
echo ""

print_info "Useful Commands:"
echo "    View logs:           docker logs -f $CONTAINER_NAME"
echo "    Stop container:      docker stop $CONTAINER_NAME"
echo "    Restart container:   docker restart $CONTAINER_NAME"
echo "    Container shell:     docker exec -it $CONTAINER_NAME /bin/bash"
echo ""

print_info "Recent Logs:"
docker logs "$CONTAINER_NAME" 2>&1 | tail -20

echo ""
print_header "Testing New concat_spaces Endpoint"

cat << EOF
Test the new endpoint with:

curl -X POST http://localhost:${PORT}/api/ffmpeg/concat_spaces \\
  -H "X-Internal-API-Key: \$YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "inputs":[
      {"spaces_key":"path/to/input1.mp4"},
      {"spaces_key":"path/to/input2.mp4"}
    ],
    "output":{"spaces_key":"path/to/output.mp4"}
  }'

Expected response:
{
  "status": "ok",
  "output_key": "path/to/output.mp4",
  "output_url": "https://..."
}
EOF

echo ""
print_success "Deployment script completed successfully!"
