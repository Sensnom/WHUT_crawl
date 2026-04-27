import asyncio
import json
from urllib.parse import urlencode

import websockets

from config import Settings


def send_napcat_message(
    settings: Settings, target: str, message: str, timeout: int = 20
) -> None:
    target_type, _, target_id = target.partition(":")
    if target_type == "group" and target_id.isdigit():
        action = "send_group_msg"
        params = {"group_id": int(target_id), "message": message}
    elif target_type == "private" and target_id.isdigit():
        action = "send_private_msg"
        params = {"user_id": int(target_id), "message": message}
    else:
        raise ValueError(f"unsupported NapCat target: {target}")

    ws_base = settings.napcat_base_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base.rstrip('/')}/"

    asyncio.get_event_loop().run_until_complete(
        _ws_send_and_recv(ws_url, action, params, settings.napcat_access_token, timeout)
    )


async def _ws_send_and_recv(
    ws_url: str,
    action: str,
    params: dict,
    token: str,
    timeout: int = 20,
) -> None:
    query = urlencode({"access_token": token})
    full_url = f"{ws_url}?{query}"

    async with websockets.connect(full_url, open_timeout=timeout, close_timeout=10) as ws:
        echo = str(id(params))
        payload = json.dumps({"action": action, "params": params, "echo": echo})
        await ws.send(payload)

        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            resp = json.loads(raw)
            if resp.get("echo") == echo:
                if resp.get("retcode") != 0 or resp.get("status") != "ok":
                    raise RuntimeError(f"NapCat WS send failed: {resp}")
                return