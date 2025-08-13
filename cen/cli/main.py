from typing import Optional
import time

import click

from cen.core.gmail import GmailClient
from cen.core.motion import MotionDetector


@click.group()
def cli() -> None:
	"""CEN - Camera Event Notifier"""


@cli.command()
@click.option("--client-id", envvar="GOOGLE_CLIENT_ID", required=True, help="Google OAuth Client ID")
@click.option("--client-secret", envvar="GOOGLE_CLIENT_SECRET", required=True, help="Google OAuth Client Secret")
@click.option("--scopes", default="https://www.googleapis.com/auth/gmail.send", show_default=True, help="OAuth scopes (comma-separated)")
@click.option("--storage", "storage", envvar="CEN_TOKEN_STORAGE", type=click.Choice(["keyring", "file"]), default="keyring", show_default=True)
@click.option("--force", is_flag=True, help="Force re-consent and get a new refresh token")
@click.option("--console", is_flag=True, help="Use console copy/paste flow (for headless/containers)")
@click.option("--open-browser/--no-open-browser", default=True, show_default=True, help="Open browser automatically (local server flow)")
@click.option("--login-hint", envvar="GMAIL_LOGIN_HINT", help="Suggest account email on Google screen")
def login(client_id: str, client_secret: str, scopes: str, storage: str, force: bool, console: bool, open_browser: bool, login_hint: Optional[str]) -> None:
	"""Open browser to sign in with Google and store tokens."""
	gmail = GmailClient(client_id=client_id, client_secret=client_secret, scopes=[s.strip() for s in scopes.split(",") if s.strip()])
	gmail.login(interactive=True, force=force, storage_backend=storage, use_console=console, open_browser=open_browser, login_hint=login_hint)
	click.echo("Login completed and credentials stored.")


@cli.command("export-token")
@click.option("--client-id", envvar="GOOGLE_CLIENT_ID", required=True)
@click.option("--client-secret", envvar="GOOGLE_CLIENT_SECRET", required=True)
@click.option("--storage", envvar="CEN_TOKEN_STORAGE", type=click.Choice(["keyring", "file"]), default="keyring", show_default=True)
def export_token(client_id: str, client_secret: str, storage: str) -> None:
	"""Print the authorized user JSON (use to set CEN_GMAIL_TOKEN_JSON env)."""
	gmail = GmailClient(client_id=client_id, client_secret=client_secret, scopes=["https://www.googleapis.com/auth/gmail.send"])
	creds = gmail.ensure_logged_in(storage_backend=storage)
	click.echo(creds.to_json())


@cli.command("test-email")
@click.option("--to", "to_email", required=True, help="Recipient email")
@click.option("--subject", default="CEN test email", show_default=True)
@click.option("--body", default="Hello from CEN", show_default=True)
@click.option("--sender", envvar="GMAIL_SENDER", help="Override sender (defaults to authenticated account)")
@click.option("--client-id", envvar="GOOGLE_CLIENT_ID", required=True)
@click.option("--client-secret", envvar="GOOGLE_CLIENT_SECRET", required=True)
@click.option("--storage", envvar="CEN_TOKEN_STORAGE", type=click.Choice(["keyring", "file"]), default="keyring", show_default=True)
def test_email(to_email: str, subject: str, body: str, sender: Optional[str], client_id: str, client_secret: str, storage: str) -> None:
	"""Send a test email via Gmail API."""
	gmail = GmailClient(client_id=client_id, client_secret=client_secret, scopes=["https://www.googleapis.com/auth/gmail.send"])
	creds = gmail.ensure_logged_in(storage_backend=storage)
	gmail.send_email(to_email=to_email, subject=subject, body_text=body, sender=sender)
	click.echo("Test email sent.")


@cli.command()
@click.option("--device-index", default=0, show_default=True, type=int, help="Camera device index (0 is default webcam)")
@click.option("--sensitivity", default=500, show_default=True, type=int, help="Minimum contour area to trigger motion")
@click.option("--min-interval-seconds", default=60, show_default=True, type=int, help="Minimum seconds between notifications")
@click.option("--to", "to_email", required=True, help="Recipient email for notifications")
@click.option("--sender", envvar="GMAIL_SENDER", help="Override sender")
@click.option("--client-id", envvar="GOOGLE_CLIENT_ID", required=True)
@click.option("--client-secret", envvar="GOOGLE_CLIENT_SECRET", required=True)
@click.option("--storage", envvar="CEN_TOKEN_STORAGE", type=click.Choice(["keyring", "file"]), default="keyring", show_default=True)
@click.option("--snapshot", is_flag=True, help="Attach a snapshot image when motion is detected")
@click.option("--subject", default="CEN motion detected", show_default=True)
@click.option("--body", default="Motion was detected by your camera.", show_default=True)
def monitor(device_index: int, sensitivity: int, min_interval_seconds: int, to_email: str, sender: Optional[str], client_id: str, client_secret: str, storage: str, snapshot: bool, subject: str, body: str) -> None:
	"""Monitor webcam and send email on motion."""
	gmail = GmailClient(client_id=client_id, client_secret=client_secret, scopes=["https://www.googleapis.com/auth/gmail.send"])
	creds = gmail.ensure_logged_in(storage_backend=storage)

	detector = MotionDetector(device_index=device_index, min_contour_area=sensitivity)
	click.echo("Starting motion detection. Press Ctrl+C to stop.")

	last_sent_at = 0.0
	try:
		for event in detector.detect_events():
			if time.time() - last_sent_at < max(1, min_interval_seconds):
				continue
			attachment = None
			if snapshot and event.frame is not None:
				retval, buf = event.encode_jpeg()
				if retval:
					attachment = ("snapshot.jpg", buf, "image/jpeg")
			gmail.send_email(
				to_email=to_email,
				subject=subject,
				body_text=body,
				sender=sender,
				attachment=attachment,
			)
			last_sent_at = time.time()
			click.echo("Notification sent.")
	except KeyboardInterrupt:
		click.echo("Stopping monitor...")
	finally:
		detector.close()
