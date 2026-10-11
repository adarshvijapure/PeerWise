"""
Google Drive Service
--------------------
Handles OAuth2-authenticated uploads to Google Drive using the user's
own credentials (drive.file scope – only files this app creates).

Usage in a route:
    drive = DriveService(current_user)
    link = drive.upload_file(file_storage_obj, folder_name="StudyGroup Uploads")
"""

import io
import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

from flask import current_app
from app.extensions import db

logger = logging.getLogger(__name__)

# Scopes requested during OAuth login (must match auth route)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveService:
    """
    Thin wrapper around the Google Drive v3 REST API.
    Instantiate with a User ORM object to use their stored OAuth tokens.
    """

    def __init__(self, user):
        self.user = user
        self._service = None

    # ── Credential management ─────────────────────────────────────────────

    def _get_credentials(self) -> Credentials:
        """Build google.oauth2.Credentials from the stored user tokens."""
        cfg = current_app.config
        creds = Credentials(
            token=self.user.access_token,
            refresh_token=self.user.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=cfg["GOOGLE_CLIENT_ID"],
            client_secret=cfg["GOOGLE_CLIENT_SECRET"],
            scopes=SCOPES,
        )
        # Auto-refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Persist the new access token
            self.user.access_token = creds.token
            if creds.expiry:
                self.user.token_expiry = creds.expiry.replace(tzinfo=timezone.utc)
            db.session.commit()
            logger.info("Access token refreshed for user %s", self.user.email)
        return creds

    def _get_service(self):
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    # ── Folder helpers ────────────────────────────────────────────────────

    def _get_or_create_folder(self, folder_name: str) -> str:
        """
        Returns the Drive folder ID for `folder_name`, creating it if absent.
        Only searches within files created by this app (drive.file scope).
        """
        service = self._get_service()
        query = (
            f"name='{folder_name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )
        results = service.files().list(q=query, fields="files(id,name)").execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        # Create folder
        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(body=metadata, fields="id").execute()
        logger.info("Created Drive folder '%s' (id=%s)", folder_name, folder["id"])
        return folder["id"]

    # ── Public API ────────────────────────────────────────────────────────

    def upload_file(
        self,
        file_storage,            # werkzeug.datastructures.FileStorage
        folder_name: str = "StudyGroup Uploads",
        make_public: bool = True,
    ) -> str:
        """
        Upload a file to Google Drive under `folder_name`.
        Returns a shareable web link (viewable by anyone with the link).
        """
        service = self._get_service()
        folder_id = self._get_or_create_folder(folder_name)

        file_bytes = file_storage.read()
        mime_type = file_storage.content_type or "application/octet-stream"
        filename = file_storage.filename

        file_metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype=mime_type,
            resumable=True,
        )

        try:
            uploaded = (
                service.files()
                .create(body=file_metadata, media_body=media, fields="id,webViewLink")
                .execute()
            )
        except HttpError as exc:
            logger.error("Drive upload failed for user %s: %s", self.user.email, exc)
            raise

        file_id = uploaded.get("id")
        web_link = uploaded.get("webViewLink")

        if make_public:
            web_link = self._make_public(service, file_id) or web_link

        logger.info("Uploaded '%s' → Drive id=%s | link=%s", filename, file_id, web_link)
        return web_link

    def _make_public(self, service, file_id: str) -> str | None:
        """Grant 'anyone with the link' read access and return the view URL."""
        try:
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()
            meta = service.files().get(
                fileId=file_id, fields="webViewLink"
            ).execute()
            return meta.get("webViewLink")
        except HttpError as exc:
            logger.warning("Could not make file %s public: %s", file_id, exc)
            return None

    def delete_file(self, file_id: str) -> bool:
        """Permanently delete a Drive file. Returns True on success."""
        service = self._get_service()
        try:
            service.files().delete(fileId=file_id).execute()
            logger.info("Deleted Drive file id=%s", file_id)
            return True
        except HttpError as exc:
            logger.error("Could not delete Drive file %s: %s", file_id, exc)
            return False
