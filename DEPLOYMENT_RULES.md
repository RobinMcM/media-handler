# Deployment Rules: Media API Domain

This repository serves media processing APIs on `media.rapidmvp.io`.

## Fixed Domain Mapping

- Public host: `media.rapidmvp.io`
- Droplet: `178.62.113.38`
- Do not route this service through `models.rapidmvp.io`.

## TLS Requirements

- HTTPS is mandatory for all public API traffic.
- Port 80 is only for ACME challenge and HTTP -> HTTPS redirect.
- Certificate files must resolve to:
  - `/etc/letsencrypt/live/media.rapidmvp.io/fullchain.pem`
  - `/etc/letsencrypt/live/media.rapidmvp.io/privkey.pem`
- Cert renewal must remain enabled (`certbot renew` service).

## Nginx Configuration Rules

- Active SSL host file:
  - `nginx/conf.d/media.rapidmvp.io.conf`
- HTTP-only file is bootstrap-only:
  - `nginx/conf.d/media.rapidmvp.io-http-only.conf`
- Once SSL works, disable HTTP-only config (rename away from `.conf`).

## Verification Gates

1. DNS resolves:
   - `dig +short media.rapidmvp.io` -> `178.62.113.38`
2. HTTPS health:
   - `curl -I https://media.rapidmvp.io/health` -> `200`
3. Auth API check:
   - `curl -H "X-Internal-API-Key: <KEY>" https://media.rapidmvp.io/api/instructions`
4. Media API endpoints needed by MovieShaker are reachable and authenticated.

## MovieShaker Integration Rule

- MovieShaker media env must use:
  - `MEDIA_HANDLER_URL=https://media.rapidmvp.io`
