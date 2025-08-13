# CEN - Camera Event Notifier (CLI)

MVP: Detect motion via Razer webcam and email a notification with snapshot using Gmail OAuth.

## Features
- CLI-based: `cen login`, `cen monitor`, `cen test-email`
- Google OAuth via browser (Continue with Google) and token persistence
- Motion detection using OpenCV; threshold + area filtering
- Dockerized; logs to stdout

## Quickstart
1. Python 3.10+
2. `pip install -e .`
3. `cen login` to open browser and authenticate Gmail
4. `cen test-email --to you@example.com`
5. `cen monitor --device-index 0 --sensitivity 500 --min-interval-seconds 60 --to you@example.com`

## Environment
- Set required env vars before running:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
- Optional:
  - `GMAIL_SENDER` (defaults to authenticated account)
  - `CEN_TOKEN_STORAGE` (`keyring` or `file`) default: `keyring`

No additional config files are created by default. Tokens are stored in OS keyring unless `CEN_TOKEN_STORAGE=file`.

## Docker
Build and run:
```bash
# build
docker build -t cen:latest .

# Option A: Host login (recommended for Windows) – opens your browser automatically
cen login --login-hint "$env:GMAIL_LOGIN_HINT"  # set to your Gmail address

# Optionally export token JSON to feed into Compose env (avoids keyring in container)
cen export-token > token.json
setx CEN_GMAIL_TOKEN_JSON "$(Get-Content token.json -Raw)"

# Option B: In-container login (headless) – copies a URL, paste the code back
# docker compose run --rm cen-cli cen login --console --no-open-browser

# Linux camera via Compose (maps /dev/video0) – requires CEN_GMAIL_TOKEN_JSON or keyring in container
setx CEN_TO you@example.com
setx GOOGLE_CLIENT_ID your_client_id
setx GOOGLE_CLIENT_SECRET your_client_secret
# For Windows, monitor is best run on host due to camera limitations in Docker Desktop

docker compose run --rm cen-cli cen test-email --to %CEN_TO%
# Linux only (camera mapping):
docker compose run --rm --profile linuxCamera cen-monitor
```

Notes:
- On Windows with Razer Kiyo, Docker Desktop cannot access the webcam directly. Run `cen monitor` on the host:
  ```powershell
  .\.venv\Scripts\cen monitor --to you@example.com --snapshot
  ```
- For containers, prefer providing `CEN_GMAIL_TOKEN_JSON` to avoid keyring dependencies.
