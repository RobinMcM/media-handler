#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
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
FFmpeg Stack Deployment Script (with Valkey)

Usage: $0 [OPTIONS]

Options:
    --no-pull           Skip git pull (use local changes)
    --env-file PATH     Path to .env file (default: /root/media-handler/.env)
    -h, --help          Show this help message

Environment Variables Required (in .env file):
    INTERNAL_API_KEYS           Comma-separated API keys
    SPACES_BUCKET               DigitalOcean Spaces bucket name
    SPACES_ENDPOINT             Spaces endpoint URL
    SPACES_ACCESS_KEY_ID        Spaces access key
    SPACES_SECRET_ACCESS_KEY    Spaces secret key
    SPACES_PUBLIC_BASE_URL      (Optional) Public base URL for Spaces
    VALKEY_URL                  (Optional) Valkey connection URL (default: redis://valkey:6379)
    MEDIA_DIR                   (Optional) Media files directory (default: /root/media-files)

Services Deployed:
    - ffmpeg-api (port 8000)
    - valkey (port 127.0.0.1:6379, not publicly exposed)

Examples:
    # Standard deployment
    ./deploy-ffmpeg-stack.sh

    # Deploy without git pull
    ./deploy-ffmpeg-stack.sh --no-pull

    # Use custom env file
    ./deploy-ffmpeg-stack.sh --env-file /path/to/.env
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

print_header "FFmpeg Stack Deployment (Docker Compose)"
print_info "Environment file: $ENV_FILE"
echo ""

# Step 1: Check Docker Compose
print_header "Step 1: Verifying Docker Compose"

if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    print_success "docker-compose found"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    print_success "docker compose (plugin) found"
else
    print_error "Docker Compose not found"
    echo ""
    print_info "Please install Docker Compose:"
    echo "    https://docs.docker.com/compose/install/"
    exit 1
fi

COMPOSE_VERSION=$($COMPOSE_CMD version --short 2>/dev/null || $COMPOSE_CMD version 2>/dev/null | head -n1)
print_info "Version: $COMPOSE_VERSION"

# Step 2: Git Pull (optional)
if [ "$DO_GIT_PULL" = true ]; then
    print_header "Step 2: Pulling Latest Changes"
    
    if [ -d .git ]; then
        print_info "Pulling from git repository..."
        if git pull origin master 2>&1; then
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

# Step 3: Verify environment file exists
print_header "Step 3: Checking Environment Configuration"

if [ ! -f "$ENV_FILE" ]; then
    print_error "Environment file not found: $ENV_FILE"
    echo ""
    print_info "Please create $ENV_FILE based on .env.example:"
    echo "    cp .env.example $ENV_FILE"
    echo "    # Then edit $ENV_FILE with your actual values"
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

if [ -z "$VALKEY_URL" ]; then
    print_info "VALKEY_URL not set (using default: redis://valkey:6379)"
fi

# Step 4: Stop existing containers
print_header "Step 4: Stopping Existing Containers"

print_info "Stopping stack..."
$COMPOSE_CMD down 2>&1 || true
print_success "Old containers stopped and removed"

# Step 5: Build and start services
print_header "Step 5: Building and Starting Services"

print_info "Building images..."
if $COMPOSE_CMD build --no-cache; then
    print_success "Images built successfully"
else
    print_error "Build failed"
    exit 1
fi

print_info "Starting services..."
if $COMPOSE_CMD up -d; then
    print_success "Services started"
else
    print_error "Failed to start services"
    exit 1
fi

# Step 6: Wait for services to be ready
print_header "Step 6: Verifying Deployment"

print_info "Waiting for services to start..."
sleep 5

# Check running services
print_info "Checking service status..."
$COMPOSE_CMD ps

# Check ffmpeg-api health
print_info "Testing ffmpeg-api health endpoint..."
sleep 2

if curl -s -f "http://localhost:8000/health" > /dev/null 2>&1; then
    HEALTH_RESPONSE=$(curl -s "http://localhost:8000/health")
    print_success "FFmpeg API health check passed: $HEALTH_RESPONSE"
else
    print_error "FFmpeg API health check failed"
    echo ""
    print_info "Showing container logs:"
    docker logs ffmpeg-api 2>&1 | tail -20
    exit 1
fi

# Check Valkey health
print_info "Testing Valkey connection..."
if docker exec valkey valkey-cli ping > /dev/null 2>&1; then
    VALKEY_RESPONSE=$(docker exec valkey valkey-cli ping)
    print_success "Valkey health check passed: $VALKEY_RESPONSE"
else
    print_error "Valkey health check failed"
    echo ""
    print_info "Showing Valkey logs:"
    docker logs valkey 2>&1 | tail -20
    exit 1
fi

# Verify ffmpeg-api can see Valkey environment variable
print_info "Verifying Valkey connectivity from ffmpeg-api..."
VALKEY_URL_CHECK=$(docker exec ffmpeg-api sh -c 'echo $VALKEY_URL' 2>/dev/null || echo "not set")
if [ "$VALKEY_URL_CHECK" != "not set" ]; then
    print_success "VALKEY_URL in ffmpeg-api: $VALKEY_URL_CHECK"
else
    print_warning "VALKEY_URL not set in ffmpeg-api container"
fi

# Step 7: Show deployment summary
print_header "Deployment Complete"

echo -e "${GREEN}✓ FFmpeg Stack deployed successfully!${NC}\n"

print_info "Services Running:"
echo "    - ffmpeg-api (container: ffmpeg-api)"
echo "    - valkey     (container: valkey)"
echo ""

print_info "Network:"
echo "    Name:       ffmpeg-network"
echo "    Type:       bridge"
echo ""

print_info "Volumes:"
echo "    valkey_data:    /data (persistent Valkey storage)"
echo ""

print_info "Ports:"
echo "    FFmpeg API:     8000 (public)"
echo "    Valkey:         127.0.0.1:6379 (localhost only, not exposed)"
echo ""

print_info "FFmpeg API Endpoints:"
echo "    Health:              http://localhost:8000/health"
echo "    Instructions:        http://localhost:8000/api/instructions"
echo "    Logs:                http://localhost:8000/api/logs"
echo "    Concat (local):      http://localhost:8000/api/ffmpeg/concat"
echo "    Concat (spaces):     http://localhost:8000/api/ffmpeg/concat_spaces"
echo ""

print_info "Useful Commands:"
echo "    View all logs:       $COMPOSE_CMD logs -f"
echo "    View API logs:       docker logs -f ffmpeg-api"
echo "    View Valkey logs:    docker logs -f valkey"
echo "    Stop stack:          $COMPOSE_CMD down"
echo "    Restart stack:       $COMPOSE_CMD restart"
echo "    Service status:      $COMPOSE_CMD ps"
echo "    Valkey CLI:          docker exec -it valkey valkey-cli"
echo "    API shell:           docker exec -it ffmpeg-api sh"
echo ""

print_info "Valkey Management:"
echo "    Check connection:    docker exec -it valkey valkey-cli ping"
echo "    Monitor commands:    docker exec -it valkey valkey-cli monitor"
echo "    Get info:            docker exec -it valkey valkey-cli info"
echo "    Data location:       Named volume 'valkey_data'"
echo ""

print_info "Recent FFmpeg API Logs:"
docker logs ffmpeg-api 2>&1 | tail -15

echo ""
print_success "Deployment script completed successfully!"
print_info "Stack is ready for high-load testing and request coordination"
