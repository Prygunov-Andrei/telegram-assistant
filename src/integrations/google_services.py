from __future__ import annotations

import base64
import email.utils
import functools
import json
import logging
import re
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
    "https://www.googleapis.com/auth/drive",
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
        data = self._gmail_service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = data.get("messages", [])
        result = []
        for msg in messages:
            full = self._gmail_service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
            headers = full.get("payload", {}).get("headers", [])
            mapped = {h.get("name", "").lower(): h.get("value", "") for h in headers}
            labels = full.get("labelIds", [])
            result.append({
                "id": msg["id"],
                "subject": mapped.get("subject", ""),
                "from": mapped.get("from", ""),
                "date": mapped.get("date", ""),
                "snippet": full.get("snippet", ""),
                "is_unread": "UNREAD" in labels,
                "has_attachments": bool(self._list_attachments(full.get("payload", {}))),
            })
        return result

    def gmail_get_message(self, message_id: str) -> dict[str, Any]:
        full = self._gmail_service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        headers = {
            h["name"].lower(): h["value"]
            for h in full.get("payload", {}).get("headers", [])
        }
        body = self._extract_body(full.get("payload", {}))
        attachments = self._list_attachments(full.get("payload", {}))
        labels = full.get("labelIds", [])
        return {
            "id": message_id,
            "thread_id": full.get("threadId", ""),
            "subject": headers.get("subject", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "date": headers.get("date", ""),
            "message_id_header": headers.get("message-id", ""),
            "snippet": full.get("snippet", ""),
            "body": body[:10_000],
            "labels": labels,
            "is_unread": "UNREAD" in labels,
            "attachments": attachments,
        }

    def _extract_body(self, payload: dict) -> str:
        """Рекурсивное извлечение текста из email payload."""
        mime = payload.get("mimeType", "")
        parts = payload.get("parts", [])

        # Простое сообщение без частей
        if not parts:
            data = payload.get("body", {}).get("data", "")
            if data:
                text = base64.urlsafe_b64decode(data)
                charset = self._get_charset(payload)
                decoded = text.decode(charset, errors="replace")
                if "html" in mime:
                    return self._trim_quoted(self._strip_html(decoded))
                return self._trim_quoted(decoded)
            return ""

        # Multipart — ищем text/plain, fallback на text/html
        plain = ""
        html = ""
        for part in parts:
            part_mime = part.get("mimeType", "")
            if part_mime == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    charset = self._get_charset(part)
                    plain = base64.urlsafe_b64decode(data).decode(charset, errors="replace")
            elif part_mime == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    charset = self._get_charset(part)
                    html = base64.urlsafe_b64decode(data).decode(charset, errors="replace")
            elif "multipart" in part_mime:
                # Рекурсия для nested multipart
                nested = self._extract_body(part)
                if nested:
                    return nested

        if plain:
            return self._trim_quoted(plain)
        if html:
            return self._trim_quoted(self._strip_html(html))
        return ""

    @staticmethod
    def _get_charset(part: dict) -> str:
        for header in part.get("headers", []):
            if header.get("name", "").lower() == "content-type":
                val = header.get("value", "")
                match = re.search(r"charset=[\"']?([^\s;\"']+)", val, re.IGNORECASE)
                if match:
                    return match.group(1)
        return "utf-8"

    @staticmethod
    def _strip_html(html: str) -> str:
        from src.utils.formatting import strip_html
        return strip_html(html)

    @staticmethod
    def _trim_quoted(text: str) -> str:
        lines = text.split("\n")
        result = []
        in_quote = False
        for line in lines:
            stripped = line.strip()
            if re.match(r"^On .+ wrote:$", stripped):
                result.append("[цитата обрезана]")
                break
            if stripped.startswith(">"):
                if not in_quote:
                    in_quote = True
                    result.append("[цитата обрезана]")
                continue
            in_quote = False
            result.append(line)
        return "\n".join(result)

    def _list_attachments(self, payload: dict) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []
        self._collect_attachments(payload, attachments)
        return attachments

    def _collect_attachments(self, part: dict, out: list[dict[str, Any]]) -> None:
        filename = part.get("filename", "")
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            out.append({
                "filename": filename,
                "mimeType": part.get("mimeType", ""),
                "size": body.get("size", 0),
                "attachmentId": body["attachmentId"],
            })
        for sub in part.get("parts", []):
            self._collect_attachments(sub, out)

    def gmail_get_attachment(self, message_id: str, attachment_id: str, size_limit: int = 5 * 1024 * 1024) -> bytes:
        data = (
            self._gmail_service.users().messages().attachments()
            .get(userId="me", id=attachment_id, messageId=message_id)
            .execute()
        )
        raw = data.get("data", "")
        decoded = base64.urlsafe_b64decode(raw)
        if len(decoded) > size_limit:
            raise ValueError(f"Attachment too large: {len(decoded)} bytes (limit {size_limit})")
        return decoded

    def gmail_send(self, to_email: str, subject: str, body: str) -> str:
        raw = (
            f"To: {to_email}\r\n"
            f"Subject: {subject}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"\r\n{body}"
        )
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")
        out = self._gmail_service.users().messages().send(
            userId="me", body={"raw": encoded}
        ).execute()
        return out.get("id", "")

    def gmail_reply(self, message_id: str, body: str) -> str:
        original = self.gmail_get_message(message_id)
        thread_id = original["thread_id"]
        orig_msg_id = original["message_id_header"]
        subject = original["subject"]
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        to = original["from"]

        raw = (
            f"To: {to}\r\n"
            f"Subject: {subject}\r\n"
            f"In-Reply-To: {orig_msg_id}\r\n"
            f"References: {orig_msg_id}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"\r\n{body}"
        )
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")
        out = self._gmail_service.users().messages().send(
            userId="me", body={"raw": encoded, "threadId": thread_id}
        ).execute()
        return out.get("id", "")

    def gmail_forward(self, message_id: str, to_email: str) -> str:
        original = self.gmail_get_message(message_id)
        fwd_body = (
            f"---------- Forwarded message ----------\n"
            f"From: {original['from']}\n"
            f"Date: {original['date']}\n"
            f"Subject: {original['subject']}\n"
            f"To: {original['to']}\n\n"
            f"{original['body']}"
        )
        subject = original["subject"]
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"
        return self.gmail_send(to_email, subject, fwd_body)

    def gmail_archive(self, message_id: str) -> None:
        self._gmail_service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
        ).execute()

    def gmail_delete(self, message_id: str) -> None:
        self._gmail_service.users().messages().delete(userId="me", id=message_id).execute()

    def gmail_mark_read(self, message_id: str) -> None:
        self._gmail_service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def gmail_mark_unread(self, message_id: str) -> None:
        self._gmail_service.users().messages().modify(
            userId="me", id=message_id, body={"addLabelIds": ["UNREAD"]}
        ).execute()

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

    def drive_upload_file(
        self, content: bytes, filename: str,
        mime_type: str = "application/octet-stream",
        folder_id: str = "root",
    ) -> dict[str, str]:
        from googleapiclient.http import MediaInMemoryUpload
        media = MediaInMemoryUpload(content, mimetype=mime_type)
        metadata: dict[str, Any] = {"name": filename, "parents": [folder_id]}
        f = self._drive_service.files().create(
            body=metadata, media_body=media, fields="id,webViewLink",
        ).execute()
        return {"id": f["id"], "webViewLink": f.get("webViewLink", "")}

    def drive_create_folder(self, name: str, parent_id: str = "root") -> dict[str, str]:
        metadata: dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        f = self._drive_service.files().create(
            body=metadata, fields="id,webViewLink",
        ).execute()
        return {"id": f["id"], "webViewLink": f.get("webViewLink", "")}

    def drive_move_file(self, file_id: str, new_parent_id: str) -> None:
        f = self._drive_service.files().get(fileId=file_id, fields="parents").execute()
        old_parents = ",".join(f.get("parents", []))
        self._drive_service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=old_parents,
        ).execute()

    def drive_get_link(self, file_id: str) -> str:
        f = self._drive_service.files().get(
            fileId=file_id, fields="webViewLink",
        ).execute()
        return f.get("webViewLink", "")

    def drive_delete_file(self, file_id: str) -> None:
        self._drive_service.files().update(
            fileId=file_id, body={"trashed": True},
        ).execute()
