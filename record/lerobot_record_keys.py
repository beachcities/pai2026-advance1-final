#!/usr/bin/env python3
"""lerobot-record を、Enter で次へ進めるようにして起動する（引数は lerobot-record と同じ）。

lerobot 0.4.4 のキーは → 次へ / ← 録り直し / Esc 終了だけ。この画面では → が届かず Enter は届いたので、
  Enter または →           : 次へ（録画中ならその 1 本を終える。置き直し中なら置き直しを終える）
  Backspace または ←       : その 1 本を録り直す
  Esc                      : 録画をやめる（それまでの分は保存）
に置き換える。キーは X11 の窓（record_so101.sh が開く灰色の窓）を選んでいるときに届く。
"""
import logging

import lerobot.scripts.lerobot_record as rec
from lerobot.utils.control_utils import is_headless


def init_keyboard_listener():
    events = {"exit_early": False, "rerecord_episode": False, "stop_recording": False}
    if is_headless():
        logging.warning("Headless environment detected. Keyboard inputs will not be available.")
        return None, events
    from pynput import keyboard

    def on_press(key):
        if key in (keyboard.Key.enter, keyboard.Key.right):
            print("Enter: 次へ", flush=True)
            events["exit_early"] = True
        elif key in (keyboard.Key.backspace, keyboard.Key.left):
            print("Backspace: 録り直し", flush=True)
            events["rerecord_episode"] = True
            events["exit_early"] = True
        elif key == keyboard.Key.esc:
            print("Esc: 録画をやめます", flush=True)
            events["stop_recording"] = True
            events["exit_early"] = True

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    return listener, events


rec.init_keyboard_listener = init_keyboard_listener

if __name__ == "__main__":
    rec.main()
