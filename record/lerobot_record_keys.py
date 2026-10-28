#!/usr/bin/env python3
"""lerobot-record を、Enter で次へ進めるようにして起動する（引数は lerobot-record と同じ）。

lerobot 0.4.4 のキーは → 次へ / ← 録り直し / Esc 終了だけ。この画面では → が届かず Enter は届いたので、
  Enter または →           : 次へ（録画中ならその 1 本を終える。置き直し中なら置き直しを終える）
  Backspace または ←       : その 1 本を録り直す
  Esc                      : 録画をやめる（それまでの分は保存）
に置き換える。キーは X11 の窓（record_so101.sh が開く灰色の窓）を選んでいるときに届く。
- 押しっぱなしのくり返しと、1.5 秒以内の 2 回目は無視する。録画・置き直しが始まる前に押された Enter も捨てる
  （持ち越すと、始まったばかりの区間が 0 秒で終わり、動かすタイミングがずれるため）。
- 最初の 1 本の前は「準備」の区間にして、Enter を押すまで録画を始めない。
- それでも 1 本が 0 フレームで終わったら、エラーで止めずに「録り直し」にする。
"""
import logging
import time

import lerobot.scripts.lerobot_record as rec
from lerobot.utils.control_utils import is_headless


def init_keyboard_listener():
    events = {"exit_early": False, "rerecord_episode": False, "stop_recording": False}
    if is_headless():
        logging.warning("Headless environment detected. Keyboard inputs will not be available.")
        return None, events
    from pynput import keyboard

    held = set()
    last = [0.0]

    def on_release(key):
        held.discard(key)

    def on_press(key):
        if key in held:  # 押しっぱなしのくり返し
            return
        held.add(key)
        now = time.monotonic()
        if now - last[0] < 1.5:
            print("（続けて押されたので無視しました）", flush=True)
            return
        last[0] = now
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

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener, events


_record_loop = rec.record_loop


_waited = [False]


def record_loop(*args, **kwargs):
    dataset, events = kwargs.get("dataset"), kwargs.get("events")
    if dataset is not None and events is not None and not _waited[0]:
        # 最初の 1 本の前に「準備」の区間を入れる（腕は付いてくるが保存しない）。Enter で 1 本目の録画が始まる
        _waited[0] = True
        print("準備中：Enter を押すと 1 本目の録画が始まります", flush=True)
        prep = {k: v for k, v in kwargs.items()
                if k not in ("dataset", "policy", "preprocessor", "postprocessor", "display_compressed_images")}
        prep["control_time_s"] = 3600
        events["exit_early"] = False
        _record_loop(**prep)
        if events["stop_recording"]:
            return
        print("録画を始めます", flush=True)
    # 始まる前（前の 1 本の保存中など）に押された Enter は捨てる。持ち越すと、この区間が 0 秒で終わる
    if events is not None:
        events["exit_early"] = False
    _record_loop(*args, **kwargs)
    if dataset is not None and events is not None and dataset.episode_buffer is not None \
            and dataset.episode_buffer["size"] == 0 and not events["stop_recording"]:
        print("この 1 本は 0 フレームで終わったので、録り直しにします", flush=True)
        events["rerecord_episode"] = True


rec.init_keyboard_listener = init_keyboard_listener
rec.record_loop = record_loop

if __name__ == "__main__":
    rec.main()
