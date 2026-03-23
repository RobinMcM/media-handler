# HTTPS Setup for media.rapidmvp.io

Quick guide to enable HTTPS for your Media Handler API.

## Prerequisites

- DNS `A` record is configured:
  - `media.rapidmvp.io` -> `178.62.113.38`
- Ports `80` and `443` are open on Droplet B firewall.

## Recommended Setup

On Droplet B:

```bash
cd /path/to/media-handler
git pull origin master
chmod +x setup-https.sh
./setup-https.sh
```

The script will:

1. bring stack down
2. run HTTP-only nginx for ACME challenge
3. issue Let's Encrypt certificate for `media.rapidmvp.io`
4. restore SSL nginx config
5. restart nginx and auto-renew certbot service

## Manual Certificate Command

If you need to issue manually:

```bash
docker compose run --rm --entrypoint "" certbot certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d media.rapidmvp.io
```

## Verification

```bash
curl -I https://media.rapidmvp.io/health
curl -H "X-Internal-API-Key: YOUR_KEY" https://media.rapidmvp.io/api/instructions
```

## Renewal

Auto-renew runs in the `certbot` service. You can test renewal manually:

```bash
docker compose run --rm --entrypoint "" certbot certbot renew --dry-run
docker compose restart nginx
```
