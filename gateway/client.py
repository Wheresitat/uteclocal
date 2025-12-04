from __future__ import annotations

import datetime as dt
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - handled in __init__
    httpx = None  # type: ignore

from .config import GatewayConfig


class UtecCloudClient:
    """Thin wrapper around the U-tec open API.

    The concrete endpoints are intentionally simple and easy to change if
    the published API differs. All requests include the configured access
    key and secret key in headers.
    """

    def __init__(self, config: GatewayConfig) -> None:
        if httpx is None:
            raise RuntimeError(
                "httpx is required to call the U-tec cloud API; install dependencies from requirements.txt"
            )
        self._config = config
        self._client = httpx.AsyncClient(timeout=15.0)

    def _base_url(self) -> str:
        base_url = (self._config.get("base_url") or "").strip()
        if not base_url:
            raise ValueError("Base URL is not configured")
        return base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._config.get("access_key"):
            headers["X-Access-Key"] = self._config["access_key"]
        if self._config.get("secret_key"):
            headers["X-Secret-Key"] = self._config["secret_key"]
        if self._config.get("access_token"):
            headers["Authorization"] = f"Bearer {self._config['access_token']}"
        return headers

    async def fetch_devices(self) -> list[dict[str, Any]]:
        url = f"{self._base_url()}/devices"
        resp = await self._client.get(url, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get("devices") or data.get("payload", {}).get("devices", []) or []
        if isinstance(data, list):
            return data
        return []

    async def fetch_status(self, device_id: str) -> dict[str, Any]:
        url = f"{self._base_url()}/devices/{device_id}/status"
        resp = await self._client.get(url, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {"payload": {"devices": []}}

    async def send_lock(self, device_id: str, target: str) -> dict[str, Any]:
        url = f"{self._base_url()}/devices/{device_id}/{target}"
        resp = await self._client.post(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    async def exchange_code(self, code: str, redirect_uri: str, *, code_verifier: str | None = None) -> dict[str, Any]:
        url = f"{self._base_url()}/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._config.get("client_id"),
            "client_secret": self._config.get("client_secret"),
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            payload["code_verifier"] = code_verifier
        resp = await self._client.post(url, data=payload, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def refresh_token(self) -> dict[str, Any] | None:
        refresh_token = self._config.get("refresh_token")
        if not refresh_token:
            return None
        url = f"{self._base_url()}/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._config.get("client_id"),
            "client_secret": self._config.get("client_secret"),
        }
        resp = await self._client.post(url, data=payload, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        if "expires_in" in data:
            expiry = dt.datetime.utcnow() + dt.timedelta(seconds=int(data["expires_in"]))
            data["token_expires_at"] = expiry.isoformat()
        return data

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "UtecCloudClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.aclose()
