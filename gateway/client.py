from __future__ import annotations

from typing import Any

from urllib.parse import urljoin

import logging

import httpx

from .config import GatewayConfig


class UtecCloudClient:
    """Thin wrapper around the U-tec open API.

    The concrete endpoints are intentionally simple and easy to change if
    the published API differs. All requests include the configured access
    key and secret key in headers.
    """

    def __init__(self, config: GatewayConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=15.0)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        token = (self._config.get("access_token") or "").strip()
        token_type = (self._config.get("token_type") or "Bearer").strip()
        if token:
            headers["Authorization"] = f"{token_type} {token}"
        else:
            if self._config.get("access_key"):
                headers["X-Access-Key"] = self._config["access_key"]
            if self._config.get("secret_key"):
                headers["X-Secret-Key"] = self._config["secret_key"]
            if self._config.get("scope"):
                headers["X-Scope"] = self._config["scope"]
        return headers

    async def fetch_devices(self) -> list[dict[str, Any]]:
        devices_path = self._config.get("devices_path") or "/openapi/v1/devices"
        url = urljoin(self._config["base_url"].rstrip("/") + "/", devices_path.lstrip("/"))
        logging.getLogger(__name__).info("Requesting devices from %s", url)
        resp = await self._client.get(url, headers=self._headers(), follow_redirects=True)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            logging.getLogger(__name__).warning("Device list was not JSON: %s", resp.text[:500])
            raise
        if isinstance(data, dict):
            return data.get("devices") or data.get("payload", {}).get("devices", []) or []
        if isinstance(data, list):
            return data
        return []

    async def fetch_status(self, device_id: str) -> dict[str, Any]:
        url = f"{self._config['base_url'].rstrip('/')}/devices/{device_id}/status"
        resp = await self._client.get(url, headers=self._headers(), follow_redirects=True)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            logging.getLogger(__name__).warning("Status response was not JSON: %s", resp.text[:500])
            raise
        if isinstance(data, dict):
            return data
        return {"payload": {"devices": []}}

    async def send_lock(self, device_id: str, target: str) -> dict[str, Any]:
        url = f"{self._config['base_url'].rstrip('/')}/devices/{device_id}/{target}"
        resp = await self._client.post(url, headers=self._headers(), follow_redirects=True)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "UtecCloudClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.aclose()
