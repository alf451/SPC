from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from edge_agent.models import Reading
from edge_agent.sources.base import Source

# Mappa minimale dei codici USB HID Usage ID (keyboard/keypad page, 0x07) per le
# cifre, il punto decimale, il segno meno e Invio — sufficiente per decodificare
# l'output di un convertitore USB-ITN (es. Mitutoyo IT-016U), che emula una
# tastiera numerica standard.
_HID_KEYPAD_MAP: dict[int, str] = {
    0x27: "0", 0x1E: "1", 0x1F: "2", 0x20: "3", 0x21: "4",
    0x22: "5", 0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9",
    0x2D: "-", 0x37: ".", 0x63: ".",  # 0x37=period tastiera principale, 0x63=keypad "."
    0x28: "\n", 0x2B: "\n",           # Enter, Tab (alcuni convertitori terminano con Tab)
}


class DigimaticUSBHIDSource(Source):
    """Legge un convertitore USB-ITN che emula una tastiera (es. Mitutoyo IT-016U).

    Limite noto: se sullo stesso PC sono collegati più convertitori USB-ITN,
    un hook a livello di sistema operativo (fallback `keyboard`) non distingue
    fisicamente da quale dispositivo arriva l'input — in quel caso è necessario
    il path hidapi per-device (`device_path` in config), che apre l'handle HID
    specifico invece di un hook globale.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.port = config.get("device_path") or "usb-hid"
        self.channel_no = None
        self._device_path = config.get("device_path")
        self._poll_interval_ms = config.get("poll_interval_ms", 50)

    async def read(self) -> AsyncIterator[Reading]:
        if self._device_path:
            async for reading in self._read_hidapi():
                yield reading
        else:
            async for reading in self._read_global_keyboard_fallback():
                yield reading

    # --- percorso preferito: handle HID dedicato al dispositivo -----------

    async def _read_hidapi(self) -> AsyncIterator[Reading]:
        import hid  # import locale: dipendenza opzionale, non disponibile su tutte le piattaforme

        device = hid.device()
        await asyncio.to_thread(device.open_path, self._device_path.encode())
        device.set_nonblocking(False)

        buffer = ""
        try:
            while True:
                report = await asyncio.to_thread(device.read, 8)
                if not report:
                    await asyncio.sleep(self._poll_interval_ms / 1000)
                    continue

                # byte 2 del report HID keyboard standard è il primo keycode premuto
                keycode = report[2] if len(report) > 2 else 0
                char = _HID_KEYPAD_MAP.get(keycode)
                if char is None:
                    continue
                if char == "\n":
                    value = _to_float(buffer)
                    yield Reading(
                        port=self.port,
                        channel_no=None,
                        raw_value=value,
                        raw_text=buffer,
                        captured_at=datetime.now(timezone.utc),
                    )
                    buffer = ""
                else:
                    buffer += char
        finally:
            await asyncio.to_thread(device.close)

    # --- fallback: hook tastiera globale (singolo convertitore per PC) ----

    async def _read_global_keyboard_fallback(self) -> AsyncIterator[Reading]:
        import keyboard  # import locale: dipendenza opzionale (richiede permessi elevati su alcuni OS)

        queue: asyncio.Queue[str] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        buffer = ""

        def on_key_event(event: keyboard.KeyEvent) -> None:
            nonlocal buffer
            if event.event_type != "down":
                return
            if event.name in ("enter", "tab"):
                loop.call_soon_threadsafe(queue.put_nowait, buffer)
                buffer = ""
            elif len(event.name) == 1 and (event.name.isdigit() or event.name in "-."):
                buffer += event.name

        keyboard.hook(on_key_event)
        try:
            while True:
                raw_text = await queue.get()
                yield Reading(
                    port=self.port,
                    channel_no=None,
                    raw_value=_to_float(raw_text),
                    raw_text=raw_text,
                    captured_at=datetime.now(timezone.utc),
                )
        finally:
            keyboard.unhook(on_key_event)


def _to_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None
