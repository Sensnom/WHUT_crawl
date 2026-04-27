import asyncio
import json
from pathlib import Path

import pytest

from napcat_sender import send_napcat_message


def make_settings(tmp_path: Path):
    from config import Settings

    return Settings(
        api_key="k",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        request_timeout=60,
        output_dir=str(tmp_path),
        napcat_base_url="http://localhost:8095",
        napcat_access_token="token",
    )


def test_send_napcat_message_rejects_invalid_target(tmp_path: Path):
    settings = make_settings(tmp_path)

    with pytest.raises(ValueError, match="unsupported NapCat target"):
        send_napcat_message(settings, "channel:123456", "hello")


@pytest.mark.integration
def test_send_napcat_message_integration(tmp_path: Path):
    settings = make_settings(tmp_path)
    import websockets

    async def run():
        ws_base = settings.napcat_base_url.replace("http://", "ws://")
        ws_url = f"{ws_base.rstrip('/')}/"
        query = f"access_token={settings.napcat_access_token}"
        full_url = f"{ws_url}?{query}"

        async with websockets.connect(full_url, open_timeout=10, close_timeout=10) as ws:
            echo = "test-echo"
            msg = json.dumps(
                {"action": "send_private_msg", "params": {"user_id": 2902341094, "message": "integration test"}, "echo": echo}
            )
            await ws.send(msg)
            while True:
                raw = await ws.recv()
                resp = json.loads(raw)
                if resp.get("echo") == echo:
                    assert resp.get("retcode") == 0
                    return

    asyncio.get_event_loop().run_until_complete(run())