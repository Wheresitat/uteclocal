from __future__ import annotations

import datetime as dt
from typing import Any, TypedDict


class DeviceState(TypedDict, total=False):
    id: str
    name: str
    type: str
    data: dict[str, Any]
    last_updated: str
    available: bool
    error: str | None


class BridgeStatus(TypedDict, total=False):
    running: bool
    last_poll: str | None
    error: str | None
    token_valid: bool
    token_expiry: str | None
    poller_running: bool


class OAuthChallenge(TypedDict):
    state: str
    code_verifier: str
    expires_at: dt.datetime


class BridgeState:
    """In-memory state shared between API routes and the poller."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceState] = {}
        self._last_poll: dt.datetime | None = None
        self._error: str | None = None
        self._token_expiry: dt.datetime | None = None
        self._oauth_challenge: OAuthChallenge | None = None
        self._poller_running: bool = False

    def set_devices(self, devices: list[dict[str, Any]]) -> None:
        now_iso = dt.datetime.utcnow().isoformat()
        for dev in devices:
            device_id = str(dev.get("id"))
            self._devices[device_id] = {
                "id": device_id,
                "name": dev.get("name") or f"U-tec Device {device_id}",
                "type": dev.get("type") or "lock",
                "data": dev,
                "last_updated": now_iso,
                "available": True,
                "error": None,
            }
        self._last_poll = dt.datetime.utcnow()
        self._error = None

    def update_device(self, device_id: str, data: dict[str, Any], *, available: bool = True, error: str | None = None) -> None:
        now_iso = dt.datetime.utcnow().isoformat()
        existing = self._devices.get(device_id) or {
            "id": device_id,
            "name": data.get("name") or f"U-tec Device {device_id}",
            "type": data.get("type") or "lock",
        }
        existing.update({
            "data": data,
            "last_updated": now_iso,
            "available": available,
            "error": error,
        })
        self._devices[device_id] = existing  # type: ignore[assignment]
        self._last_poll = dt.datetime.utcnow()
        self._error = None

    def set_error(self, message: str) -> None:
        self._error = message

    def set_poller_running(self, running: bool) -> None:
        self._poller_running = running

    def set_token_expiry(self, expiry: dt.datetime | None) -> None:
        self._token_expiry = expiry

    def set_oauth_challenge(self, challenge: OAuthChallenge | None) -> None:
        self._oauth_challenge = challenge

    def get_oauth_challenge(self) -> OAuthChallenge | None:
        return self._oauth_challenge

    # Accessors
    def devices(self) -> list[DeviceState]:
        return list(self._devices.values())

    def device(self, device_id: str) -> DeviceState | None:
        return self._devices.get(device_id)

    def status(self) -> BridgeStatus:
        return {
            "running": True,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "error": self._error,
            "token_valid": self._token_expiry is not None and self._token_expiry > dt.datetime.utcnow(),
            "token_expiry": self._token_expiry.isoformat() if self._token_expiry else None,
            "poller_running": self._poller_running,
        }


STATE = BridgeState()

