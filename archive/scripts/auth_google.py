#!/usr/bin/env python3
"""OAuth2 flow for Google Calendar + Contacts.

Usage:
    python3 scripts/auth_google.py

Opens browser for Google login. Saves token to ~/.gmail-mcp/calendar_credentials.json
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/drive.readonly",
]

KEYS_FILE = Path.home() / ".gmail-mcp" / "gcp-oauth.keys.json"
OUTPUT_FILE = Path.home() / ".gmail-mcp" / "calendar_credentials.json"


def main() -> None:
    if not KEYS_FILE.exists():
        print(f"ERROR: OAuth keys file not found: {KEYS_FILE}")
        print("Download it from Google Cloud Console → Credentials → OAuth 2.0 Client IDs")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(KEYS_FILE), scopes=SCOPES)
    creds = flow.run_local_server(port=8090)

    token_data = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": SCOPES,
    }
    OUTPUT_FILE.write_text(json.dumps(token_data, indent=2))
    print(f"Token saved to {OUTPUT_FILE}")
    print("Add to config/.env:")
    print(f"  GOOGLE_CALENDAR_TOKEN_PATH={OUTPUT_FILE}")


if __name__ == "__main__":
    main()
