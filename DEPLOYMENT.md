# Deployment Guide

## Localhost

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.server
```

Open `http://localhost:3000/register`.

## Local HTTPS

Generate a self-signed certificate:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/key.pem -out certs/cert.pem -days 365 -subj "/CN=localhost"
```

Set:

```bash
HTTPS_ENABLED=true
HTTPS_KEY_PATH=./certs/key.pem
HTTPS_CERT_PATH=./certs/cert.pem
EXPECTED_ORIGIN=https://localhost:3000
RP_ID=localhost
```

Run:

```bash
python -m src.server
```

## Cloudflare Tunnel

### Named tunnel

Use a stable hostname for cross-device credential reuse.

```bash
cloudflared tunnel create passless
cloudflared tunnel route dns passless passless.example.com
cloudflared tunnel run passless --url http://localhost:3000
```

Set:

```bash
RP_ID=passless.example.com
EXPECTED_ORIGIN=https://passless.example.com
```

### Quick tunnel

Useful for temporary testing:

```bash
cloudflared tunnel --url http://localhost:3000
```

Set:

```bash
ALLOW_TRYCLOUDFLARE_ORIGIN=true
```

## ngrok

```bash
ngrok http 3000
```

Set:

```bash
ALLOW_NGROK_ORIGIN=true
```

## Notes

- `http://localhost` is allowed for development.
- For remote devices, use HTTPS or a tunnel.
- For cross-device login, keep the hostname stable.
