# QR deployment modes

## A — This PC is the server (default)

The Windows PC runs the API, database and file vault. The launcher binds to 127.0.0.1 and starts at port 8765, automatically selecting the next available port when that port is occupied. Set the `QR_PORT` environment variable to choose another starting port. The server remains local-only and works without internet. LAN access is a separate operator action requiring a deliberate bind to 0.0.0.0 and Windows Firewall rules.

## B — Remote host

Install the same QR API on another computer or VPS. Give it a stable HTTPS origin, configure QR_CORS_ORIGINS to allow the UI origin, and enter the API origin in QR → Подключение. The remote host becomes the data server; the PC is a client.

## Production target

Local desktop storage: SQLCipher SQLite, encrypted file vault and Windows DPAPI. Remote server: PostgreSQL, private object storage, TLS reverse proxy, separate migration/runtime roles, backups and restore tests. The current MVP uses unencrypted SQLite on whichever host runs the API. Remote endpoint selection is implemented in the UI, but production VPS hardening, PostgreSQL, sync, encryption and licensing remain future work. Never assume that a public IP makes the development server safe.
