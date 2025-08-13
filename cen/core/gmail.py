import base64
import json
import os
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Optional, Sequence, Tuple

import keyring
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SERVICE_NAME = "cen-gmail"
TOKEN_USERNAME = "cen-user"


@dataclass
class GmailClient:
	client_id: str
	client_secret: str
	scopes: Sequence[str] = tuple(GMAIL_SCOPES)
	_cached_creds: Optional[Credentials] = field(default=None, init=False, repr=False)

	def _validate_oauth_config(self) -> None:
		"""Validate OAuth configuration and provide helpful error messages."""
		if not self.client_id:
			raise ValueError("Google OAuth Client ID is required. Set GOOGLE_CLIENT_ID environment variable.")
		if not self.client_secret:
			raise ValueError("Google OAuth Client Secret is required. Set GOOGLE_CLIENT_SECRET environment variable.")
		if not self.client_id.endswith('.apps.googleusercontent.com'):
			raise ValueError(
				f"Invalid Client ID format: {self.client_id}\n"
				"Client ID should end with '.apps.googleusercontent.com'\n"
				"Get your Client ID from Google Cloud Console: https://console.cloud.google.com/apis/credentials"
			)
		
		# List of required redirect URIs that should be configured in Google Cloud Console
		required_uris = [
			"http://localhost:8080/",
			"http://localhost:8081/",
			"http://localhost:8082/",
			"http://localhost:8090/",
			"http://localhost:9000/",
			"http://localhost:9001/",
			"http://localhost:9090/",
			"http://localhost:9091/"
		]
		
		print("ℹ️  OAuth Configuration Check:")
		print(f"   Client ID: {self.client_id}")
		print("   Required redirect URIs in Google Cloud Console:")
		for uri in required_uris:
			print(f"   - {uri}")
		print("\n   Configure these URIs at: https://console.cloud.google.com/apis/credentials")

	def _load_credentials_from_keyring(self) -> Optional[Credentials]:
		try:
			serialized = keyring.get_password(SERVICE_NAME, TOKEN_USERNAME)
			if not serialized:
				return None
			info = json.loads(serialized)
			creds = Credentials.from_authorized_user_info(info, scopes=self.scopes)
			if creds and creds.expired and creds.refresh_token:
				creds.refresh(Request())
			return creds
		except Exception:
			return None

	def _save_credentials_to_keyring(self, creds: Credentials) -> None:
		try:
			keyring.set_password(SERVICE_NAME, TOKEN_USERNAME, creds.to_json())
		except Exception:
			# Fallback to file storage if keyring fails (e.g., in containers)
			self._save_credentials_to_file(creds)

	def _load_credentials_from_file(self, path: str = "token.json") -> Optional[Credentials]:
		if not os.path.exists(path):
			return None
		try:
			creds = Credentials.from_authorized_user_file(path, self.scopes)
			if creds and creds.expired and creds.refresh_token:
				creds.refresh(Request())
			return creds
		except Exception:
			return None

	def _save_credentials_to_file(self, creds: Credentials, path: str = "token.json") -> None:
		with open(path, "w", encoding="utf-8") as f:
			f.write(creds.to_json())

	def _load_credentials_from_env(self) -> Optional[Credentials]:
		raw = os.getenv("CEN_GMAIL_TOKEN_JSON") or os.getenv("GMAIL_AUTHORIZED_USER") or os.getenv("GMAIL_TOKEN_JSON")
		if not raw:
			return None
		try:
			info = json.loads(raw)
			creds = Credentials.from_authorized_user_info(info, scopes=self.scopes)
			if creds and creds.expired and creds.refresh_token:
				creds.refresh(Request())
			return creds
		except Exception:
			return None

	def login(self, interactive: bool = True, force: bool = False, storage_backend: str = "keyring", use_console: bool = False, open_browser: bool = True, login_hint: Optional[str] = None) -> Credentials:
		# Validate OAuth configuration first
		self._validate_oauth_config()
		
		# Standard ports for OAuth redirect URIs
		standard_ports = [8080, 8081, 8082, 8090, 9000, 9001, 9090, 9091]
		redirect_uris = [f"http://localhost:{port}/" for port in standard_ports]
		redirect_uris.append("http://localhost/")  # Fallback
		
		client_config = {
			"installed": {
				"client_id": self.client_id,
				"client_secret": self.client_secret,
				"auth_uri": "https://accounts.google.com/o/oauth2/auth",
				"token_uri": "https://oauth2.googleapis.com/token",
				"redirect_uris": redirect_uris,
				"auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
			}
		}

		creds: Optional[Credentials] = None
		if not force:
			if storage_backend == "keyring":
				creds = self._load_credentials_from_keyring()
			else:
				creds = self._load_credentials_from_file()

		if not creds or not creds.valid:
			if creds and creds.expired and creds.refresh_token:
				creds.refresh(Request())
			else:
				flow = InstalledAppFlow.from_client_config(client_config, self.scopes)
				extra_kwargs = {"access_type": "offline", "prompt": "consent"}
				if login_hint:
					extra_kwargs["login_hint"] = login_hint
				if use_console:
					# For headless/console flow, start a temporary server to catch the callback
					import threading
					import http.server
					import socketserver
					import urllib.parse
					from queue import Queue
					
					# Find an available port
					import socket
					sock = socket.socket()
					sock.bind(('', 0))
					port = sock.getsockname()[1]
					sock.close()
					
					# Set up the redirect URI for this port
					redirect_uri = f"http://localhost:{port}/"
					client_config["installed"]["redirect_uris"] = [redirect_uri]
					flow = InstalledAppFlow.from_client_config(client_config, self.scopes)
					
					# Queue to capture the authorization code
					code_queue = Queue()
					
					class CallbackHandler(http.server.BaseHTTPRequestHandler):
						def do_GET(self):
							query = urllib.parse.urlparse(self.path).query
							params = urllib.parse.parse_qs(query)
							if 'code' in params:
								code_queue.put(params['code'][0])
								self.send_response(200)
								self.send_header('Content-type', 'text/html')
								self.end_headers()
								self.wfile.write(b'<html><body><h1>Authorization successful!</h1><p>You can close this window and return to the terminal.</p></body></html>')
							else:
								self.send_response(400)
								self.send_header('Content-type', 'text/html')
								self.end_headers()
								self.wfile.write(b'<html><body><h1>Authorization failed!</h1><p>No code received.</p></body></html>')
						
						def log_message(self, format, *args):
							pass  # Suppress server logs
					
					# Start temporary server
					httpd = socketserver.TCPServer(("", port), CallbackHandler)
					server_thread = threading.Thread(target=httpd.serve_forever)
					server_thread.daemon = True
					server_thread.start()
					
					try:
						auth_url, _ = flow.authorization_url(**extra_kwargs)
						print(f"\nPlease visit this URL to authorize the application:")
						print(f"{auth_url}")
						print(f"\nWaiting for authorization... (Press Ctrl+C to cancel)")
						
						# Wait for the callback
						code = code_queue.get(timeout=300)  # 5 minute timeout
						flow.fetch_token(code=code)
						creds = flow.credentials
						print("Authorization successful!")
					finally:
						httpd.shutdown()
						httpd.server_close()
				else:
					# Try ports that match our configured redirect URIs
					ports_to_try = [8080, 8081, 8082, 8090, 9000, 9001, 9090, 9091]
					creds = None
					for port in ports_to_try:
						try:
							# Ensure the redirect URI matches what's in our config
							redirect_uri = f"http://localhost:{port}/"
							creds = flow.run_local_server(
								port=port, 
								open_browser=open_browser,
								bind_addr="localhost",
								**extra_kwargs
							)
							break
						except OSError as e:
							print(f"Port {port} unavailable: {e}")
							continue
						except Exception as e:
							print(f"OAuth error on port {port}: {e}")
							continue
					if not creds:
						error_msg = (
							"❌ OAuth authentication failed on all ports!\n\n"
							"Common solutions:\n"
							"1. Configure redirect URIs in Google Cloud Console:\n"
							"   https://console.cloud.google.com/apis/credentials\n"
							"   Add these URIs to your OAuth 2.0 Client:\n"
							f"   {', '.join([f'http://localhost:{p}/' for p in ports_to_try])}\n\n"
							"2. Use console authentication: --console flag\n"
							"3. Ensure ports 8080-9091 are available\n"
							"4. Check firewall settings\n"
							"5. Verify Client ID and Secret are correct"
						)
						raise RuntimeError(error_msg)

			if storage_backend == "keyring":
				self._save_credentials_to_keyring(creds)
			else:
				self._save_credentials_to_file(creds)

		return creds

	def ensure_logged_in(self, storage_backend: str = "keyring") -> Credentials:
		if self._cached_creds and self._cached_creds.valid:
			return self._cached_creds

		creds = self._load_credentials_from_env()
		if not creds:
			if storage_backend == "keyring":
				creds = self._load_credentials_from_keyring()
			else:
				creds = self._load_credentials_from_file()
		if not creds:
			creds = self.login(interactive=True, storage_backend=storage_backend)
		self._cached_creds = creds
		return creds

	def _build_service(self, creds: Credentials):
		return build("gmail", "v1", credentials=creds, cache_discovery=False)

	def send_email(
		self,
		to_email: str,
		subject: str,
		body_text: str,
		sender: Optional[str] = None,
		attachment: Optional[Tuple[str, bytes, str]] = None,
	) -> str:
		creds = self._cached_creds or self.ensure_logged_in()
		service = self._build_service(creds)

		message = EmailMessage()
		message["To"] = to_email
		if sender:
			message["From"] = sender
		message["Subject"] = subject
		message.set_content(body_text)

		if attachment is not None:
			filename, data, mime_type = attachment
			main_type, sub_type = mime_type.split("/", 1)
			message.add_attachment(data, maintype=main_type, subtype=sub_type, filename=filename)

		encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
		create_message = {"raw": encoded_message}

		try:
			response = (
				service.users().messages().send(userId="me", body=create_message).execute()
			)
			return response.get("id", "")
		except HttpError as e:
			raise RuntimeError(f"Gmail send failed: {e}")
