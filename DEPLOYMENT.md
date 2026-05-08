# Deployment Guide

This guide covers local development, local HTTPS, Windows setup, and Cloudflare Tunnel usage for cross-device testing.

## 1. Localhost development

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.server
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m src.server
```

Default local settings:

```env
RP_ID=localhost
EXPECTED_ORIGIN=http://localhost:3000
```

Open `http://localhost:3000/register` or `http://localhost:3000/login`.

## 2. Local HTTPS

WebAuthn requires a secure context for non-localhost origins. For development on localhost, you can generate a self-signed certificate.

### Generate a certificate

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -days 365 \
  -subj "/CN=localhost"
```

### Enable HTTPS

```env
HTTPS_ENABLED=true
HTTPS_KEY_PATH=./certs/key.pem
HTTPS_CERT_PATH=./certs/cert.pem
EXPECTED_ORIGIN=https://localhost:3000
RP_ID=localhost
```

Run the server again with `python -m src.server`.

## 3. Windows notes

- Install Python and add it to `PATH`.
- Use PowerShell for the virtual environment activation command shown above.
- If OpenSSL is not available natively, generate the certificate from Git Bash, WSL, or use Cloudflare Tunnel instead.
- If Windows Defender Firewall prompts for access, allow Python on private networks for local testing.

## 4. Cloudflare Tunnel

Cloudflare Tunnel is the recommended way to test from multiple devices without managing a public TLS certificate.

### 4.1 Quick tunnel

Start the app locally, then expose it:

```bash
python -m src.server
cloudflared tunnel --url http://localhost:3000
```

Set:

```env
ALLOW_TRYCLOUDFLARE_ORIGIN=true
```

Notes:

- The generated hostname changes each time.
- Use this mode for temporary testing.
- If you need stable cross-device passkey reuse, use a named tunnel.

### 4.2 Named tunnel

Use a fixed hostname when you want credentials created on one device to work from another device repeatedly.

```bash
cloudflared tunnel create passless
cloudflared tunnel route dns passless passless.example.com
cloudflared tunnel run passless --url http://localhost:3000
```

Set:

```env
RP_ID=passless.example.com
EXPECTED_ORIGIN=https://passless.example.com
```

## 5. ngrok

```bash
ngrok http 3000
```

Set:

```env
ALLOW_NGROK_ORIGIN=true
```

## 6. Multi-device test flow

1. Register a passkey on one browser/device.
2. Reopen the same site from another browser/device.
3. If using a quick tunnel, keep the tunnel session alive; a new tunnel hostname requires a new registration.
4. If using a named tunnel, keep `RP_ID` and `EXPECTED_ORIGIN` unchanged across devices.
5. Confirm the protected page shows the username and authenticator metadata after login.

## 7. Common origin issues

- `Invalid origin header` on localhost usually means `EXPECTED_ORIGIN` does not match the actual scheme/host/port.
- If the site is reached through Cloudflare Tunnel, the browser origin must be allowed by the tunnel settings or explicit origin list.
- The browser sends `X-Client-Origin` from the page; the backend uses it before falling back to `Origin`, `Referer`, or `Host`.
