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
