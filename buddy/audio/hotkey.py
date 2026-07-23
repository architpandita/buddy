"""Global push-to-talk hotkey listener via pynput.

Press the combo once to start recording, press it again to stop early
(otherwise recording auto-stops on silence). Requires macOS Accessibility
permission for the terminal/Python process.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from pynput import keyboard

from buddy import config


class HotkeyListener:
    def __init__(self, on_press: Callable[[], None]):
        self._on_press = on_press
        self._listener: keyboard.GlobalHotKeys | None = None
        self._triggered = threading.Event()

    def start(self) -> None:
        combo = config.HOTKEY_COMBO.replace("<alt>", "<alt_l>")
        self._listener = keyboard.GlobalHotKeys({combo: self._fire})
        self._listener.start()
        print(f"[hotkey] Push-to-talk armed on {config.HOTKEY_COMBO}")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def _fire(self) -> None:
        self._on_press()
