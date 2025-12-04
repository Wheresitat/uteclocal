import unittest
from unittest.mock import AsyncMock, patch

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - envs without FastAPI
    TestClient = None

try:
    from gateway.app import app
    from gateway.state import BridgeState
except ImportError:  # pragma: no cover - envs without FastAPI
    app = None
    BridgeState = None


class DummyClient:
    def __init__(self):
        self.calls = []

    async def send_lock(self, device_id: str, action: str):
        self.calls.append((device_id, action))
        return {"status": action, "id": device_id}

    async def aclose(self):
        return None


@unittest.skipIf(TestClient is None or app is None or BridgeState is None, "fastapi not installed")
class GatewayApiTests(unittest.TestCase):
    def _make_client(self, state: BridgeState, config: dict):
        return patch("gateway.app.STATE", state), patch("gateway.app.load_config", return_value=config), patch(
            "gateway.app.POLLING_MANAGER.start"
        )

    def test_devices_endpoint_returns_cached_state(self):
        state = BridgeState()
        state.set_devices(
            [
                {
                    "id": "lock-1",
                    "name": "Front Door",
                    "type": "lock",
                    "payload": {
                        "devices": [
                            {
                                "states": [
                                    {"capability": "st.lock", "name": "lockState", "value": "locked"},
                                    {"capability": "st.batteryLevel", "name": "level", "value": 90},
                                ]
                            }
                        ]
                    },
                }
            ]
        )

        patches = self._make_client(state, {"base_url": "https://api.example.com"})
        with patches[0], patches[1], patches[2]:
            with TestClient(app) as client:
                resp = client.get("/api/devices")

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()["payload"]["devices"]
        self.assertEqual(len(payload), 1)
        device = payload[0]
        self.assertEqual(device["id"], "lock-1")
        self.assertEqual(device["name"], "Front Door")
        states = device["data"]["payload"]["devices"][0]["states"]
        lock_state = next(s for s in states if s["capability"] == "st.lock")
        self.assertEqual(lock_state["value"], "locked")

    def test_device_detail_not_found(self):
        state = BridgeState()
        patches = self._make_client(state, {"base_url": "https://api.example.com"})
        with patches[0], patches[1], patches[2]:
            with TestClient(app) as client:
                resp = client.get("/api/devices/missing")
        self.assertEqual(resp.status_code, 404)

    def test_lock_command_uses_client(self):
        state = BridgeState()
        dummy = DummyClient()
        patches = self._make_client(state, {"base_url": "https://api.example.com"})
        with patches[0], patches[1], patches[2], patch("gateway.app._with_client", AsyncMock(return_value=dummy)):
            with TestClient(app) as client:
                resp = client.post("/api/devices/lock-1/lock")

        self.assertEqual(resp.status_code, 200)
        self.assertIn(("lock-1", "lock"), dummy.calls)

    def test_token_and_secrets_masked_in_status(self):
        state = BridgeState()
        config = {
            "base_url": "https://api.example.com",
            "client_id": "id",
            "client_secret": "secret",
            "access_token": "abc",
            "refresh_token": "ref",
        }
        patches = self._make_client(state, config)
        with patches[0], patches[1], patches[2]:
            with TestClient(app) as client:
                resp = client.get("/api/status")

        self.assertEqual(resp.status_code, 200)
        config_resp = resp.json()["config"]
        self.assertEqual(config_resp["client_secret"], "***")
        self.assertEqual(config_resp["access_token"], "***")
        self.assertEqual(config_resp["refresh_token"], "***")


if __name__ == "__main__":
    unittest.main()
