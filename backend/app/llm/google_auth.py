from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx


class GoogleAccessTokenProvider:
    """Access tokens from local user ADC or the Cloud Run metadata server."""

    def __init__(self, *, credentials_path: str, project_id: str) -> None:
        self.project_id = project_id
        self.credentials: dict = {}
        if credentials_path:
            self.credentials = json.loads(Path(credentials_path).read_text())
            if self.credentials.get("type") != "authorized_user":
                raise ValueError(
                    "The REST client supports gcloud user ADC or Cloud Run metadata ADC"
                )
        self.quota_project_id = self.credentials.get("quota_project_id") or project_id
        self._access_token = ""
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token

        async with self._lock:
            if self._access_token and time.time() < self._expires_at - 60:
                return self._access_token
            payload = (
                await self._user_adc_token()
                if self.credentials
                else await self._metadata_token()
            )
            self._access_token = payload["access_token"]
            self._expires_at = time.time() + int(payload.get("expires_in", 3600))
            return self._access_token

    async def _user_adc_token(self) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.credentials["client_id"],
                    "client_secret": self.credentials["client_secret"],
                    "refresh_token": self.credentials["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
        response.raise_for_status()
        return response.json()

    async def _metadata_token(self) -> dict:
        url = (
            "http://metadata.google.internal/computeMetadata/v1/"
            "instance/service-accounts/default/token"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers={"Metadata-Flavor": "Google"})
        response.raise_for_status()
        return response.json()
