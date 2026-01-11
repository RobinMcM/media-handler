# Valkey (Redis-compatible) Setup Guide

## Overview

Valkey is a high-performance, Redis-compatible key-value store running as a second container in the FFmpeg stack. It provides:
- **Request coordination** for high-load scenarios
- **Rate limiting** and throttling
- **Caching** for expensive operations
- **Job queuing** (future use)

**Security:** Valkey is NOT exposed publicly. It only listens on `127.0.0.1:6379` and is accessible within the Docker network.

---

## Architecture

```
┌─────────────────┐         ┌──────────────┐
│   ffmpeg-api    │◄────────┤    valkey    │
│  (port 8000)    │  redis://valkey:6379  │
│                 │         │ (port 6379)  │
└─────────────────┘         └──────────────┘
         │                         │
         └─────── ffmpeg-network ──┘
```

### Services
- **ffmpeg-api**: Main FastAPI service (public port 8000)
- **valkey**: Redis-compatible cache (localhost-only port 6379)

### Networking
- Both containers run on `ffmpeg-network` bridge network
- ffmpeg-api connects to Valkey via `redis://valkey:6379`
- Valkey port 6379 is bound to `127.0.0.1` only (not `0.0.0.0`)

### Data Persistence
- Valkey data stored in Docker named volume: `valkey_data`
- AOF (Append-Only File) enabled for durability
- Data survives container restarts

---

## Deployment

### Start the Stack

```bash
cd /root/media-handler
./deploy-ffmpeg-stack.sh
```

This will:
1. Pull latest git changes (optional: use `--no-pull` to skip)
2. Validate environment configuration
3. Build Docker images
4. Start both ffmpeg-api and Valkey containers
5. Run health checks
6. Display service status

### Stop the Stack

```bash
cd /root/media-handler
docker compose down
```

This stops and removes containers but **preserves Valkey data** in the named volume.

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart only Valkey
docker compose restart valkey

# Restart only ffmpeg-api
docker compose restart ffmpeg-api
```

---

## Health Checks

### 1. Check Valkey Health

```bash
# From host
docker exec -it valkey valkey-cli ping
```

**Expected output:** `PONG`

### 2. Check Valkey From ffmpeg-api

```bash
# Verify environment variable
docker exec -it ffmpeg-api sh -c 'echo $VALKEY_URL'

# Expected: redis://valkey:6379
```

### 3. Check Service Status

```bash
docker compose ps
```

**Expected:**
```
NAME        IMAGE               STATUS
ffmpeg-api  ffmpeg-api:latest   Up (healthy)
valkey      valkey/valkey:7     Up (healthy)
```

---

## Valkey Management

### Access Valkey CLI

```bash
docker exec -it valkey valkey-cli
```

Once inside the CLI:
```bash
# Test connection
127.0.0.1:6379> PING
PONG

# Get server info
127.0.0.1:6379> INFO

# List all keys
127.0.0.1:6379> KEYS *

# Get a specific key
127.0.0.1:6379> GET some-key

# Monitor real-time commands
127.0.0.1:6379> MONITOR

# Exit
127.0.0.1:6379> EXIT
```

### Common CLI Commands (From Host)

```bash
# Ping check
docker exec valkey valkey-cli ping

# Get server info
docker exec valkey valkey-cli info

# Get memory stats
docker exec valkey valkey-cli info memory

# Get all keys
docker exec valkey valkey-cli keys '*'

# Monitor commands in real-time
docker exec -it valkey valkey-cli monitor

# Get specific key value
docker exec valkey valkey-cli get "mykey"

# Check database size
docker exec valkey valkey-cli dbsize
```

---

## Configuration

### Current Settings (docker-compose.yml)

```yaml
command: >
  valkey-server
  --appendonly yes              # Enable AOF for durability
  --maxmemory 512mb             # Memory limit
  --maxmemory-policy noeviction # Don't evict keys when full
```

### Tuning for Production

Edit `docker-compose.yml` to adjust:

**For high-throughput caching:**
```yaml
--maxmemory 2gb
--maxmemory-policy allkeys-lru  # Evict least-recently-used keys
```

**For job queues (no eviction):**
```yaml
--maxmemory 1gb
--maxmemory-policy noeviction   # Fail writes when full (safe for queues)
```

After changing config:
```bash
docker compose down
docker compose up -d
```

---

## Data Location

### Named Volume

```bash
# Inspect volume
docker volume inspect valkey_data

# Show volume location
docker volume inspect valkey_data -f '{{ .Mountpoint }}'
```

### Backup Valkey Data

```bash
# Create backup
docker exec valkey valkey-cli BGSAVE

# Copy dump file from container
docker cp valkey:/data/dump.rdb ./valkey-backup-$(date +%Y%m%d-%H%M%S).rdb
```

### Restore Valkey Data

```bash
# Stop Valkey
docker compose stop valkey

# Copy backup into volume (requires root)
docker run --rm -v valkey_data:/data -v $(pwd):/backup alpine \
  cp /backup/dump.rdb /data/dump.rdb

# Start Valkey
docker compose start valkey
```

---

## Logs

### View Valkey Logs

```bash
# Follow logs
docker logs -f valkey

# Last 50 lines
docker logs valkey --tail 50

# Logs since 10 minutes ago
docker logs valkey --since 10m
```

### View All Stack Logs

```bash
# Follow all services
docker compose logs -f

# Only Valkey
docker compose logs -f valkey

# Only ffmpeg-api
docker compose logs -f ffmpeg-api
```

---

## Security

### Current Security Posture

✅ **NOT exposed publicly:**
- Port binding: `127.0.0.1:6379:6379` (localhost only)
- Only accessible from host and ffmpeg-network containers

✅ **No authentication required:**
- Safe for internal-only deployment
- Add Redis password if needed: `--requirepass YOUR_PASSWORD`

✅ **Firewall:**
- Valkey is NOT reachable from the internet
- Only ffmpeg-api can connect via Docker network

### Adding Authentication (Optional)

Edit `docker-compose.yml`:

```yaml
valkey:
  command: >
    valkey-server
    --appendonly yes
    --maxmemory 512mb
    --maxmemory-policy noeviction
    --requirepass YOUR_STRONG_PASSWORD
```

Update `.env`:
```bash
VALKEY_URL=redis://:YOUR_STRONG_PASSWORD@valkey:6379
```

Redeploy:
```bash
docker compose down
docker compose up -d --build
```

---

## Troubleshooting

### Valkey Not Responding

```bash
# Check if container is running
docker ps | grep valkey

# Check logs for errors
docker logs valkey --tail 50

# Restart Valkey
docker compose restart valkey
```

### ffmpeg-api Can't Connect to Valkey

```bash
# Verify network connectivity
docker exec ffmpeg-api ping -c 3 valkey

# Verify VALKEY_URL environment variable
docker exec ffmpeg-api sh -c 'echo $VALKEY_URL'

# Test connection from ffmpeg-api container
docker exec ffmpeg-api sh -c 'apk add --no-cache redis && redis-cli -h valkey ping'
```

### Valkey Out of Memory

```bash
# Check memory usage
docker exec valkey valkey-cli info memory

# Check maxmemory setting
docker exec valkey valkey-cli config get maxmemory

# Clear all data (DANGEROUS)
docker exec valkey valkey-cli FLUSHALL
```

### Volume Issues

```bash
# Remove volume and start fresh (DELETES DATA)
docker compose down -v
docker compose up -d
```

---

## Performance Monitoring

### Real-time Stats

```bash
# Watch info stats every 1 second
watch -n 1 'docker exec valkey valkey-cli info stats'

# Monitor commands as they execute
docker exec -it valkey valkey-cli monitor
```

### Key Metrics

```bash
# Commands processed per second
docker exec valkey valkey-cli info stats | grep instantaneous_ops_per_sec

# Memory usage
docker exec valkey valkey-cli info memory | grep used_memory_human

# Connected clients
docker exec valkey valkey-cli info clients | grep connected_clients

# Keyspace info (number of keys)
docker exec valkey valkey-cli info keyspace
```

---

## Next Steps

Valkey is now running and ready for integration. The ffmpeg-api can connect to it at `redis://valkey:6379`.

**Potential use cases:**
- Rate limiting for API endpoints
- Request deduplication for concat_spaces
- Caching ffprobe results
- Distributed job coordination
- Request throttling during high load

**Integration example:**
```python
import redis

# In ffmpeg-api app startup
redis_client = redis.from_url(os.getenv("VALKEY_URL", "redis://valkey:6379"))

# Test connection
redis_client.ping()  # Should return True
```

---

## Reference

- **Valkey Docs:** https://valkey.io/
- **Redis Commands:** https://redis.io/commands/ (Valkey is compatible)
- **Docker Compose:** https://docs.docker.com/compose/

---

**Created:** 2026-01-11  
**Last Updated:** 2026-01-11  
**Status:** Prototype (ready for load testing)
