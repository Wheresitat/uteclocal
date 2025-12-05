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

        # Some endpoints continue to require the access/secret key pair even
        # when an OAuth bearer token is present, so include them whenever they
        # are configured instead of treating them as mutually exclusive.
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
        """Send a lock/unlock action using the documented Command payload.

        The published example posts a `Uhome.Device/Command` payload with a
        device-level `command` containing `capability` and `name`. We attempt
        that first, then fall back to earlier `Control` shapes that have been
        observed in the field.
        """

        action_path = self._config.get("action_path") or "/action"
        url = urljoin(self._config["base_url"].rstrip("/") + "/", action_path.lstrip("/"))

        target_locked = "LOCKED" if target.lower() == "lock" else "UNLOCKED"
        lock_keyword = "lock" if target.lower() == "lock" else "unlock"

        command_payload = {
            "header": {
                "namespace": "Uhome.Device",
                "name": "Command",
                "messageId": str(uuid4()),
                "payloadVersion": "1",
            },
            "payload": {
                "devices": [
                    {
                        "id": device_id,
                        "command": {
                            "capability": "st.lock",
                            "name": lock_keyword,
                        },
                    }
                ]
            },
        }

        target_actions: list[list[dict[str, str | dict[str, str]]]] = [
            [
                {
                    "name": "LockState",
                    "value": target_locked,
                }
            ],
            [
                {
                    "name": "LockState",
                    "value": {"targetState": target_locked},
                }
            ],
            [
                {
                    "name": "Lock",
                    "value": "LOCK" if lock_keyword == "lock" else "UNLOCK",
                }
            ],
            [
                {
                    "name": "Lock",
                    "value": {"targetState": target_locked},
                }
            ],
            [
                {
                    "name": "Lock",
                    "value": {"state": "LOCK" if lock_keyword == "lock" else "UNLOCK"},
                }
            ],
            [
                {
                    "name": "Lock",
                    "value": {"value": "LOCK" if lock_keyword == "lock" else "UNLOCK"},
                }
            ],
        ]
        headers = {"Content-Type": "application/json", **self._headers()}
        log = logging.getLogger(__name__)
        last_exc: httpx.HTTPStatusError | None = None

        # Try the documented Command payload first.
        log.info("Sending %s command for %s to %s", target, device_id, url)
        resp = await self._client.post(
            url,
            headers=headers,
            json=command_payload,
            follow_redirects=True,
        )
        try:
            resp.raise_for_status()
            try:
                return resp.json() if resp.content else {}
            except ValueError:
                log.warning("Command response was not JSON: %s", resp.text[:500])
                return {"raw": resp.text}
        except httpx.HTTPStatusError as exc:
            body = exc.response.text
            detail = body or exc.response.reason_phrase
            log.warning(
                "Command payload failed (%s): %s", exc.response.status_code, detail[:500]
            )
            last_exc = exc

        # Fallbacks to older Control payloads.
        for actions in target_actions:
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
                            "actions": actions,
                        }
                    ]
                },
            }
            log.info(
                "Sending %s control (%s) for %s to %s", target, actions, device_id, url
            )
            resp = await self._client.post(
                url,
                headers=headers,
                json=payload,
                follow_redirects=True,
            )
            try:
                resp.raise_for_status()
                try:
                    return resp.json() if resp.content else {}
                except ValueError:
                    log.warning("Control response was not JSON: %s", resp.text[:500])
                    return {"raw": resp.text}
            except httpx.HTTPStatusError as exc:
                body = exc.response.text
                detail = body or exc.response.reason_phrase
                log.warning(
                    "Control attempt %s failed (%s): %s",
                    actions,
                    exc.response.status_code,
                    detail[:500],
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
