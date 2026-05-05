# Deployment Guides

This document covers deploying the WebAuthn PoC to production and for cross-device testing.

## Quick Start (Localhost)

```bash
npm install
npm run build
npm run start
```

Open `http://localhost:3000/register` in your browser.

### Environment

Default `.env` settings work for localhost:

```bash
RP_ID=localhost
EXPECTED_ORIGIN=http://localhost:3000
```

## Local HTTPS Setup

WebAuthn works best on secure origins. Generate self-signed certificates for testing:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/key.pem -out certs/cert.pem -days 365 -subj "/CN=localhost"
```

Update `.env`:

```bash
HTTPS_ENABLED=true
HTTPS_KEY_PATH=./certs/key.pem
HTTPS_CERT_PATH=./certs/cert.pem
EXPECTED_ORIGIN=https://localhost:3000
RP_ID=localhost
```

Restart server and open `https://localhost:3000/register`.

## Cloudflare Tunnel (Recommended for Production)

### Named Tunnel (Production - Stable Hostname)

1. **Install Cloudflare CLI:**

   ```bash
   # Ubuntu/Debian
   sudo apt-get install cloudflared

   # macOS
   brew install cloudflare/cloudflare/cloudflared

   # Windows: Download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
   ```

2. **Create named tunnel:**

   ```bash
   cloudflared tunnel create my-passless-app
   ```

3. **Create route in your Cloudflare zone:**

   ```bash
   cloudflared tunnel route dns my-passless-app passless.example.com
   ```

   (Replace `passless.example.com` with your domain and `example.com` must be in your Cloudflare account)

4. **Configure `.env`:**

   ```bash
   RP_ID=passless.example.com
   EXPECTED_ORIGIN=https://passless.example.com
   ALLOW_TRYCLOUDFLARE_ORIGIN=false
   ```

5. **Run tunnel:**

   ```bash
   cloudflared tunnel run my-passless-app --url http://localhost:3000
   ```

6. **Access at:** `https://passless.example.com`

**Advantage:** Fixed hostname persists across sessions. Credentials registered on `https://passless.example.com` will continue to work.

### Quick Tunnel (Testing - Changes Each Run)

```bash
cloudflared tunnel --url http://localhost:3000
```

Configure `.env`:

```bash
RP_ID=localhost
EXPECTED_ORIGIN=http://localhost:3000
ALLOW_TRYCLOUDFLARE_ORIGIN=true
```

**Warning:** Quick tunnel generates a new hostname each run. Credentials will NOT port between sessions.

## ngrok Tunnel (Alternative Testing)

### Installation

```bash
# Download from https://ngrok.com/download
# Or via package manager:
# Ubuntu: sudo snap install ngrok
# macOS: brew install ngrok
```

### Usage

1. **Start ngrok:**

   ```bash
   ngrok http 3000
   ```

   Output shows: `Forwarding https://xxxxx.ngrok.io -> http://localhost:3000`

2. **Configure `.env`:**

   ```bash
   RP_ID=localhost
   EXPECTED_ORIGIN=http://localhost:3000
   ALLOW_NGROK_ORIGIN=true
   NGROK_ORIGIN_PATTERN=^https://[a-z0-9-]+\.(?:ngrok-free\.app|ngrok\.io|ngrok\.app)$
   ```

3. **Restart server and open the tunnel URL.**

**Note:** Like quick tunnels, ngrok generates random hostnames. Credentials don't port between sessions.

## Environment Configuration Reference

### Core Settings

- `NODE_ENV` = `development | test | production`
- `HOST` = `0.0.0.0` (default, listen on all interfaces)
- `PORT` = `3000` (default)
- `RP_NAME` = `WebAuthn Passwordless` (display name)
- `RP_ID` = Relying party identifier (hostname). For localhost or quick tunnels, set to `localhost`. For production, use your stable domain.
- `EXPECTED_ORIGIN` = Full origin URL (must match browser address bar). Examples:
  - Localhost: `http://localhost:3000`
  - Local HTTPS: `https://localhost:3000`
  - Production: `https://passless.example.com`

### Additional Origins

- `EXPECTED_ORIGINS` = Comma-separated extra allowed origins (optional)

### Tunnel Support

- `ALLOW_TRYCLOUDFLARE_ORIGIN` = `true` to allow Cloudflare quick tunnel origins
- `TRYCLOUDFLARE_ORIGIN_PATTERN` = Regex for allowed quick tunnel hostnames (default matches `*.trycloudflare.com`)
- `ALLOW_NGROK_ORIGIN` = `true` to allow ngrok random hostnames
- `NGROK_ORIGIN_PATTERN` = Regex for allowed ngrok hostnames (default matches `*.ngrok-free.app`, `*.ngrok.io`, `*.ngrok.app`)

### Database & Sessions

- `DB_PATH` = SQLite file path (default: `./data/passless.db`)
- `SESSION_SECRET` = Strong random secret for session encryption (required)
- `CHALLENGE_TTL_SECONDS` = Challenge expiry in seconds (default: `300`)

### HTTPS (Direct)

- `HTTPS_ENABLED` = `true` to enable direct HTTPS (not required if using tunnel)
- `HTTPS_KEY_PATH` = Path to private key PEM file
- `HTTPS_CERT_PATH` = Path to certificate PEM file

## Deployment Checklist

- [ ] Node.js 18+ installed
- [ ] Dependencies installed: `npm install`
- [ ] `.env` configured with appropriate `RP_ID` and `EXPECTED_ORIGIN`
- [ ] Database directory writable: `mkdir -p data`
- [ ] For production: use named Cloudflare Tunnel or fixed HTTPS domain
- [ ] Session secret is strong (not default): `SESSION_SECRET`
- [ ] All tests pass: `npm run test`
- [ ] Built successfully: `npm run build`

## RP ID Selection Guide

| Scenario                  | RP_ID         | EXPECTED_ORIGIN                | Allow Tunnel?     |
| ------------------------- | ------------- | ------------------------------ | ----------------- |
| Local development         | `localhost`   | `http://localhost:3000`        | False             |
| Local HTTPS testing       | `localhost`   | `https://localhost:3000`       | False             |
| Quick Cloudflare tunnel   | `localhost`   | `http://localhost:3000`        | True (Cloudflare) |
| Named Cloudflare tunnel   | `example.com` | `https://passless.example.com` | False             |
| Production (fixed domain) | `example.com` | `https://api.example.com`      | False             |

## Cross-Device Testing

1. Use a **named tunnel** or **production domain** for stable hostname
2. Register credential on Device A: `https://passless.example.com/register`
3. Log in on Device B with same username: `https://passless.example.com/login`
4. Same passkey works if username matches

For quick/random tunnels, register the credential on each device separately (hostname changes each run).

## Troubleshooting

### "Invalid origin header"

- Verify `EXPECTED_ORIGIN` matches the address bar exactly
- Restart server after `.env` changes
- Check that server can read `.env` from repo root

### "RP ID is not a registrable domain"

- `RP_ID` must match the hostname in the address bar
- For `https://myapp.trycloudflare.com`, set `RP_ID=myapp.trycloudflare.com` or `RP_ID=localhost` with `ALLOW_TRYCLOUDFLARE_ORIGIN=true`
- Browser enforces this; it's not a server error

### Connection refused on different device

- Server must be accessible from the other device (use tunnel or public IP)
- Verify tunnel/network shows correct forwarding URL
- Firewall may block direct IP connections (use tunnel instead)

## Performance Notes

- SQLite file-based database is suitable for development and small deployments
- For scale, migrate to PostgreSQL or MySQL
- Challenge TTL affects how long registration/login pages are valid (300s default is reasonable)
- Session cookies are HttpOnly and Secure (in production)
