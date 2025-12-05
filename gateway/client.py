from __future__ import annotations

from typing import Any

from urllib.parse import urljoin

import logging

import httpx
from uuid import uuid4

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
        action_path = self._config.get("action_path") or "/action"
        url = urljoin(self._config["base_url"].rstrip("/") + "/", action_path.lstrip("/"))
        logging.getLogger(__name__).info("Requesting devices from %s", url)
        payload = {
            "header": {
                "namespace": "Uhome.Device",
                "name": "Discovery",
                "messageId": str(uuid4()),
                "payloadVersion": "1",
            },
            "payload": {},
        }
        resp = await self._client.post(
            url,
            headers={"Content-Type": "application/json", **self._headers()},
            json=payload,
            follow_redirects=True,
        )
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

    async def fetch_status(self, device_ids: list[str]) -> dict[str, Any]:
        action_path = self._config.get("action_path") or "/action"
        url = urljoin(self._config["base_url"].rstrip("/") + "/", action_path.lstrip("/"))
        logging.getLogger(__name__).info("Requesting device status from %s", url)
        payload = {
            "header": {
                "namespace": "Uhome.Device",
                "name": "Query",
                "messageId": str(uuid4()),
                "payloadVersion": "1",
            },
            "payload": {
                "devices": [{"id": device_id} for device_id in device_ids],
            },
        }
        resp = await self._client.post(
            url,
            headers={"Content-Type": "application/json", **self._headers()},
            json=payload,
            follow_redirects=True,
        )
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
        """Send a lock/unlock action using documented control payload shapes.

        The public docs show a `Uhome.Device/Control` request with an actions
        list. Some references use `LockState`/`LOCKED` instead of
        `Lock`/`LOCK`, so attempt both shapes (newer one first) to avoid 400s
        from strict payload validation.
        """

        action_path = self._config.get("action_path") or "/action"
        url = urljoin(self._config["base_url"].rstrip("/") + "/", action_path.lstrip("/"))

        action_attempts: list[tuple[str, str]] = [
            ("LockState", "LOCKED" if target.lower() == "lock" else "UNLOCKED"),
            ("Lock", target.upper()),
        ]
        headers = {"Content-Type": "application/json", **self._headers()}
        log = logging.getLogger(__name__)
        last_exc: httpx.HTTPStatusError | None = None

        for action_name, action_value in action_attempts:
            payload = {
                "header": {
                    "namespace": "Uhome.Device",
                    "name": "Control",
                    "messageId": str(uuid4()),
                    "payloadVersion": "1",
                },
                "payload": {
                    "devices": [
                        {
                            "id": device_id,
                            "actions": [
                                {
                                    "name": action_name,
                                    "value": action_value,
                                }
                            ],
                        }
                    ]
                },
            }
            log.info(
                "Sending %s control (%s=%s) for %s to %s", target, action_name, action_value, device_id, url
            )
            resp = await self._client.post(
                url,
                headers=headers,
                json=payload,
                follow_redirects=True,
            )
            try:
                resp.raise_for_status()
                return resp.json() if resp.content else {}
            except httpx.HTTPStatusError as exc:
                body = exc.response.text
                log.warning(
                    "Control attempt %s/%s failed (%s): %s", action_name, action_value, exc.response.status_code, body[:500]
                )
                last_exc = exc
                continue

        if last_exc:
            raise last_exc
        return {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "UtecCloudClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.aclose()
