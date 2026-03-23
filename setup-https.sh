#!/bin/bash
# HTTPS Setup Script for Media Handler
# Domain: media.rapidmvp.io

set -e

echo "Open Media API HTTPS Setup"
echo "==================================="
echo ""

if [ ! -f ".env" ]; then
    echo "Error: .env file not found. Make sure you're in the media-handler directory."
    exit 1
fi

read -p "Enter your email for Let's Encrypt notifications: " EMAIL

if [ -z "$EMAIL" ]; then
    echo "Error: Email is required"
    exit 1
fi

echo ""
echo "Step 1: Stopping existing containers..."
docker compose down

echo ""
echo "Step 2: Creating directories..."
mkdir -p nginx/conf.d certbot/conf certbot/www

echo ""
echo "Step 3: Enabling HTTP-only config for certificate bootstrap..."
if [ ! -f "nginx/conf.d/media.rapidmvp.io-http-only.conf" ] && [ -f "nginx/conf.d/media.rapidmvp.io-http-only.disabled" ]; then
  cp nginx/conf.d/media.rapidmvp.io-http-only.disabled nginx/conf.d/media.rapidmvp.io-http-only.conf
fi
if [ ! -f "nginx/conf.d/media.rapidmvp.io-http-only.conf" ]; then
  echo "Error: nginx/conf.d/media.rapidmvp.io-http-only.conf not found"
  exit 1
fi
if [ -f "nginx/conf.d/media.rapidmvp.io.conf" ]; then
  mv nginx/conf.d/media.rapidmvp.io.conf nginx/conf.d/media.rapidmvp.io.ssl.bak
fi
cp nginx/conf.d/media.rapidmvp.io-http-only.conf nginx/conf.d/media.rapidmvp.io.conf

echo ""
echo "Step 4: Starting services..."
docker compose up -d ffmpeg-api nginx valkey

echo ""
echo "Step 5: Waiting for services..."
sleep 8

echo ""
echo "Step 6: Requesting SSL certificate from Let's Encrypt..."
docker compose run --rm --entrypoint "" certbot certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d media.rapidmvp.io

echo ""
echo "Step 7: Restoring SSL config..."
if [ -f "nginx/conf.d/media.rapidmvp.io.ssl.bak" ]; then
  mv nginx/conf.d/media.rapidmvp.io.ssl.bak nginx/conf.d/media.rapidmvp.io.conf
fi
if [ -f "nginx/conf.d/media.rapidmvp.io-http-only.conf" ]; then
  mv nginx/conf.d/media.rapidmvp.io-http-only.conf nginx/conf.d/media.rapidmvp.io-http-only.disabled
fi

echo ""
echo "Step 8: Restarting nginx and certbot auto-renew..."
docker compose restart nginx
docker compose up -d certbot

echo ""
echo "HTTPS setup complete!"
echo ""
echo "Testing endpoints:"
echo "  - Health: curl -I https://media.rapidmvp.io/health"
echo "  - API: curl -H 'X-Internal-API-Key: YOUR_KEY' https://media.rapidmvp.io/api/instructions"
echo ""
echo "Your Media API is now secured with HTTPS at:"
echo "   - media.rapidmvp.io"
