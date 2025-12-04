import datetime as dt
import unittest
from unittest.mock import patch

import datetime as dt

from gateway import poller as poller_module
from gateway.state import BridgeState


class FakeClient:
    def __init__(self, config, devices=None, statuses=None, refresh_payload=None):
        self.config = config
        self.devices = devices or []
        self.statuses = statuses or {}
        self.refresh_payload = refresh_payload
        self.refresh_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetch_devices(self):
        return self.devices

    async def fetch_status(self, device_id):
        return self.statuses.get(device_id, {})

    async def refresh_token(self):
        self.refresh_called = True
        return self.refresh_payload


def future_iso(seconds=120):
    return (dt.datetime.utcnow() + dt.timedelta(seconds=seconds)).isoformat()


def past_iso(seconds=120):
    return (dt.datetime.utcnow() - dt.timedelta(seconds=seconds)).isoformat()


class TestPoller(unittest.IsolatedAsyncioTestCase):
    async def test_poll_once_populates_state(self):
        config = {
            "base_url": "https://api.example.com",
            "access_token": "abc",
            "token_expires_at": future_iso(),
        }
        devices = [
            {"id": "lock-1", "name": "Front", "type": "lock"},
            {"id": "lock-2", "name": "Garage", "type": "lock"},
        ]
        statuses = {
            "lock-1": {"payload": {"devices": [{"states": [{"capability": "st.lock", "name": "lockState", "value": "locked"}]}]}},
            "lock-2": {"payload": {"devices": [{"states": [{"capability": "st.batteryLevel", "name": "level", "value": 85}]}]}},
        }

        local_state = BridgeState()
        fake_client = FakeClient(config, devices=devices, statuses=statuses)
        poller = poller_module.Poller(lambda: config)

        with patch.object(poller_module, "STATE", local_state), patch(
            "gateway.poller.UtecCloudClient", return_value=fake_client
        ):
            await poller._poll_once(config)

        saved_devices = {dev["id"]: dev for dev in local_state.devices()}
        self.assertEqual(set(saved_devices.keys()), {"lock-1", "lock-2"})
        self.assertEqual(saved_devices["lock-1"]["data"], statuses["lock-1"])
        self.assertEqual(saved_devices["lock-2"]["data"], statuses["lock-2"])
        self.assertIsNone(local_state.status()["error"])

    async def test_refresh_token_when_expired(self):
        config = {
            "base_url": "https://api.example.com",
            "access_token": "old-token",
            "refresh_token": "refresh-token",
            "token_expires_at": past_iso(),
        }
        refresh_payload = {"access_token": "new-token", "expires_in": 60}
        devices = [{"id": "lock-1", "name": "Front", "type": "lock"}]
        statuses = {"lock-1": {"payload": {"devices": [{"states": []}]}}}

        local_state = BridgeState()
        fake_client = FakeClient(config, devices=devices, statuses=statuses, refresh_payload=refresh_payload)
        poller = poller_module.Poller(lambda: config)

        with patch.object(poller_module, "STATE", local_state), patch(
            "gateway.poller.save_config"
        ) as save_config, patch("gateway.poller.UtecCloudClient", return_value=fake_client):
            await poller._poll_once(config)

        self.assertEqual(config["access_token"], "new-token")
        self.assertTrue(fake_client.refresh_called)
        self.assertTrue(local_state.status()["token_valid"])
        save_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()
