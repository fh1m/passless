"""Server entrypoint and WSGI runner.

This module starts the Flask application with optional HTTPS support.

HTTPS Configuration:
- If HTTPS_ENABLED=true, loads certificate chain from HTTPS_KEY_PATH and
  HTTPS_CERT_PATH and runs with ssl.SSLContext
- Useful for development with self-signed certificates
- Production deployments typically use a reverse proxy (nginx/Caddy) for TLS

Deployment patterns:
- Development: python -m src.server (HTTP on localhost:3000)
- Local HTTPS: python -m src.server (HTTPS on localhost:3000 with self-signed cert)
- Tunnel-based: python -m src.server + cloudflared tunnel --url http://localhost:3000
"""

from __future__ import annotations

import ssl

from .app import create_app
from .config import config


def main() -> None:
    app = create_app()
    if config.https_enabled:
        if not config.https_key_path or not config.https_cert_path:
            raise RuntimeError("HTTPS_ENABLED=true requires HTTPS_KEY_PATH and HTTPS_CERT_PATH")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(config.https_key_path, config.https_cert_path)
        app.run(host=config.host, port=config.port, ssl_context=context)
        return
    app.run(host=config.host, port=config.port)


if __name__ == "__main__":
    main()
