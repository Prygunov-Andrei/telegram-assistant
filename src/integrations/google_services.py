from __future__ import annotations

import base64
import functools
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]

CONTACTS_SCOPES = [
    "https://www.googleapis.com/auth/contacts",
]

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


def _load_credentials(token_path: str, scopes: list[str]) -> Credentials:
    token_file = Path(token_path)
    if not token_file.exists():
        raise FileNotFoundError(f"Token file not found: {token_path}")

    with open(token_file, "r") as f:
        token_data = json.load(f)

    # MCP-style credentials may lack client_id/client_secret — merge from OAuth keys file
    if "client_id" not in token_data:
        keys_file = token_file.parent / "gcp-oauth.keys.json"
        if keys_file.exists():
            with open(keys_file, "r") as f:
                keys_data = json.load(f)
            oauth_keys = keys_data.get("installed", keys_data.get("web", {}))
            token_data["client_id"] = oauth_keys.get("client_id", "")
            token_data["client_secret"] = oauth_keys.get("client_secret", "")
            token_data.setdefault("token_uri", oauth_keys.get("token_uri", "https://oauth2.googleapis.com/token"))

    creds = Credentials.from_authorized_user_info(token_data, scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _try_load_credentials(token_path: str, scopes: list[str]) -> Credentials | None:
    try:
        return _load_credentials(token_path, scopes)
    except Exception as e:
        logger.warning("Could not load credentials for scopes %s: %s", scopes, e)
        return None


@dataclass
class GoogleServices:
    token_path: str
    calendar_id: str
    contacts_resource_name: str
    calendar_token_path: str = ""  # Optional separate token for Calendar/Contacts

    def __post_init__(self) -> None:
        if not self.calendar_token_path:
            self.calendar_token_path = self.token_path

    @functools.cached_property
    def _gmail_service(self):
        creds = _load_credentials(self.token_path, GMAIL_SCOPES)
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    @functools.cached_property
    def _calendar_service(self):
        creds = _load_credentials(self.calendar_token_path, CALENDAR_SCOPES)
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    @functools.cached_property
    def _people_service(self):
        creds = _load_credentials(self.calendar_token_path, CONTACTS_SCOPES)
        return build("people", "v1", credentials=creds, cache_discovery=False)

    @functools.cached_property
    def _drive_service(self):
        creds = _load_credentials(self.calendar_token_path, DRIVE_SCOPES)
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    # --- Gmail ---

    def gmail_search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        data = self._gmail_service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        messages = data.get("messages", [])
        result = []
        for msg in messages:
            full = self._gmail_service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = full.get("payload", {}).get("headers", [])
            mapped = {h.get("name", "").lower(): h.get("value", "") for h in headers}
            result.append({"id": msg["id"], "subject": mapped.get("subject", ""), "from": mapped.get("from", "")})
        return result

    def gmail_send(self, to_email: str, subject: str, body: str) -> str:
        raw = f"To: {to_email}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")
        out = self._gmail_service.users().messages().send(userId="me", body={"raw": encoded}).execute()
        return out.get("id", "")

    def gmail_archive(self, message_id: str) -> None:
        self._gmail_service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
        ).execute()

    def gmail_delete(self, message_id: str) -> None:
        self._gmail_service.users().messages().delete(userId="me", id=message_id).execute()

    # --- Calendar ---

    def calendar_list(self, time_min_iso: str, time_max_iso: str, max_results: int = 20) -> list[dict[str, Any]]:
        data = (
            self._calendar_service
            .events()
            .list(
                calendarId=self.calendar_id,
                timeMin=time_min_iso,
                timeMax=time_max_iso,
                singleEvents=True,
                orderBy="startTime",
                maxResults=max_results,
            )
            .execute()
        )
        return data.get("items", [])

    def calendar_create(self, summary: str, start_iso: str, end_iso: str, description: str = "") -> str:
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
        }
        created = self._calendar_service.events().insert(calendarId=self.calendar_id, body=event).execute()
        return created.get("id", "")

    def calendar_delete(self, event_id: str) -> None:
        self._calendar_service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()

    # --- Contacts ---

    def contacts_search(self, query: str, page_size: int = 10) -> list[dict[str, Any]]:
        data = (
            self._people_service
            .people()
            .searchContacts(
                resourceName=self.contacts_resource_name,
                query=query,
                pageSize=page_size,
                readMask="names,emailAddresses,phoneNumbers",
            )
            .execute()
        )
        return data.get("results", [])

    def contacts_create(self, given_name: str, family_name: str, email: str = "", phone: str = "") -> str:
        body: dict[str, Any] = {"names": [{"givenName": given_name, "familyName": family_name}]}
        if email:
            body["emailAddresses"] = [{"value": email}]
        if phone:
            body["phoneNumbers"] = [{"value": phone}]
        created = self._people_service.people().createContact(body=body).execute()
        return created.get("resourceName", "")

    # --- Drive ---

    def drive_search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        data = (
            self._drive_service.files()
            .list(
                q=query,
                pageSize=max_results,
                fields="files(id,name,mimeType,modifiedTime,size,webViewLink)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return data.get("files", [])

    def drive_get_file_content(self, file_id: str) -> str:
        meta = self._drive_service.files().get(fileId=file_id, fields="mimeType,name").execute()
        mime = meta.get("mimeType", "")
        # Google Docs/Sheets/Slides — export as plain text
        if mime == "application/vnd.google-apps.document":
            content = self._drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
            return content.decode("utf-8") if isinstance(content, bytes) else str(content)
        if mime == "application/vnd.google-apps.spreadsheet":
            content = self._drive_service.files().export(fileId=file_id, mimeType="text/csv").execute()
            return content.decode("utf-8") if isinstance(content, bytes) else str(content)
        if mime == "application/vnd.google-apps.presentation":
            content = self._drive_service.files().export(fileId=file_id, mimeType="text/plain").execute()
            return content.decode("utf-8") if isinstance(content, bytes) else str(content)
        # Regular files — download (limit to 100KB for text)
        if mime.startswith("text/") or mime in ("application/json", "application/xml"):
            content = self._drive_service.files().get_media(fileId=file_id).execute()
            text = content.decode("utf-8") if isinstance(content, bytes) else str(content)
            return text[:100_000]
        return f"Файл {meta.get('name', '')} ({mime}) — бинарный, нельзя показать как текст."

    def drive_list_folder(self, folder_id: str = "root", max_results: int = 20) -> list[dict[str, Any]]:
        query = f"'{folder_id}' in parents and trashed = false"
        data = (
            self._drive_service.files()
            .list(
                q=query,
                pageSize=max_results,
                fields="files(id,name,mimeType,modifiedTime,size)",
                orderBy="folder,name",
            )
            .execute()
        )
        return data.get("files", [])
