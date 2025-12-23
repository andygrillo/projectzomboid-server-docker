# Project Zomboid Server (Docker + Dashboard)

A Docker-based Project Zomboid dedicated server with a web dashboard for easy management.

## Features

- Build 42 Unstable support
- Web dashboard for server management
- One-click start/stop/restart
- Live log viewing
- CPU/Memory monitoring
- Automated backups

## Quick Start

### 1. Clone and Configure

```bash
git clone <your-repo>
cd projectzomboid-server-docker

# Copy and edit environment file
cp .env.example .env
nano .env
```

**Required settings in `.env`:**
```env
PASSWORD=your_server_password
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_admin_password
RCON_PASSWORD=your_rcon_password
SERVER_BRANCH=unstable
MEMORY_XMX_GB=6
DASHBOARD_PASSWORD=your_dashboard_password
```

### 2. Start Server + Dashboard

```bash
docker compose -f docker-compose.dashboard.yml up -d --build
```

### 3. Access

- **Game:** Connect via IP on port `16261`
- **Dashboard:** `http://your-ip:8080`

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 16261 | UDP | Game |
| 16262 | UDP | Game |
| 27015 | TCP | RCON |
| 8080 | TCP | Dashboard |

## Server Management

### Via Dashboard

Access `http://your-ip:8080` for:
- Start/Stop/Restart server
- View live logs
- Monitor CPU/Memory
- Create backups

### Via Command Line

```bash
# Start
docker compose -f docker-compose.dashboard.yml up -d

# Stop
docker compose -f docker-compose.dashboard.yml down

# View logs
docker logs -f projectzomboid

# Restart
docker compose -f docker-compose.dashboard.yml restart
```

## Backups

### Automatic (In-Game)

Configure in `.env`:
```env
BACKUPS_COUNT=10
BACKUPS_ON_START=true
BACKUPS_PERIOD=60
```

### Manual

```bash
cd ~/pz-server
tar -czf backup-$(date +%Y%m%d).tar.gz server-data
```

## File Structure

```
pz-server/
├── .env                          # Server configuration
├── docker-compose.dashboard.yml  # Docker services
├── server-files/                 # Game files (auto-downloaded)
├── server-data/                  # Saves and config
├── backups/                      # Manual backups
└── dashboard/                    # Web dashboard
    ├── app.py
    ├── Dockerfile
    └── templates/
```

## AWS EC2 Deployment

Recommended instance: **t3a.large** (2 vCPU, 8GB RAM, ~$55/mo)

Security group rules:
- UDP 16261-16262 (Game)
- TCP 27015 (RCON)
- TCP 8080 (Dashboard)
- TCP 22 (SSH)

## Troubleshooting

### Server keeps terminating
Reduce memory allocation:
```env
MEMORY_XMX_GB=6
```

### Can't connect to server
1. Check security group/firewall allows UDP 16261-16262
2. Verify server is running: `docker ps`
3. Check logs: `docker logs projectzomboid`

### Dashboard not loading
1. Check port 8080 is open
2. Verify dashboard is running: `docker ps`
3. Check logs: `docker logs pz-dashboard`

## License

MIT
