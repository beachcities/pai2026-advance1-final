#!/usr/bin/env python3
"""lerobot-record を、Enter で次へ進めるようにして起動する（引数は lerobot-record と同じ）。

lerobot 0.4.4 のキーは → 次へ / ← 録り直し / Esc 終了だけ。この画面では → が届かず Enter は届いたので、
  Enter または →           : 次へ（録画中ならその 1 本を終える。置き直し中なら置き直しを終える）
  Backspace または ←       : その 1 本を録り直す
  Esc                      : 録画をやめる（それまでの分は保存）
に置き換える。キーは、このコマンドを実行したターミナルから読む（lerobot の pynput は Wayland では届かず、
X11 の窓を使う方法は、窓の選択が外れると届かなくなったため）。
- 2 秒以内の 2 回目（押しっぱなしのくり返しを含む）は無視する。録画・置き直しが始まる前に押された Enter も捨てる
  （持ち越すと、始まったばかりの区間が 0 秒で終わり、動かすタイミングがずれるため）。
- 最初の 1 本の前は「準備」の区間にして、Enter を押すまで録画を始めない。
- それでも 1 本が 0 フレームで終わったら、エラーで止めずに「録り直し」にする。
"""
import atexit
import logging
import os
import select
import sys
import termios
import threading
import time
import tty

import lerobot.scripts.lerobot_record as rec


class _StdinKeys:
    """コマンドを実行したターミナル（標準入力）から 1 文字ずつ読む。画面の方式（Wayland/X11）や窓の選択に左右されない"""

    def __init__(self, on_key):
        self.on_key, self.fd, self.alive = on_key, sys.stdin.fileno(), True
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)  # Enter を待たずに 1 文字ずつ読む（Ctrl+C は効いたまま）
        atexit.register(self.stop)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while self.alive:
            if not select.select([self.fd], [], [], 0.2)[0]:
                continue
            c = os.read(self.fd, 1)
            if c == b"\x1b":  # Esc、または矢印キー（ESC [ C / ESC [ D）
                rest = os.read(self.fd, 2) if select.select([self.fd], [], [], 0.05)[0] else b""
                c = {b"[C": b"\n", b"[D": b"\x7f"}.get(rest, b"\x1b")
            self.on_key(c)

    def stop(self):
        if self.alive:
            self.alive = False
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)


def init_keyboard_listener():
    events = {"exit_early": False, "rerecord_episode": False, "stop_recording": False}
    if not sys.stdin.isatty():
        logging.warning("標準入力がターミナルではないので、キー操作は使えません")
        return None, events

    last = [0.0]
    keylog = open(os.environ.get("KEY_LOG", os.devnull), "a", buffering=1)

    def on_key(c: bytes):
        # 2 秒以内の 2 回目（押しっぱなしのくり返し含む）は捨てる
        now = time.monotonic()
        accepted = now - last[0] >= 2.0
        keylog.write(f"{time.strftime('%H:%M:%S')} {c!r} {'accepted' if accepted else 'ignored'}\n")
        if not accepted or c not in (b"\n", b"\r", b"\x7f", b"\x08", b"\x1b"):
            return
        last[0] = now
        if c in (b"\n", b"\r"):
            print("Enter: 次へ", flush=True)
            events["exit_early"] = True
        elif c in (b"\x7f", b"\x08"):
            print("Backspace: 録り直し", flush=True)
            events["rerecord_episode"] = True
            events["exit_early"] = True
        else:
            print("Esc: 録画をやめます", flush=True)
            events["stop_recording"] = True
            events["exit_early"] = True

    return _StdinKeys(on_key), events


_record_loop = rec.record_loop


_waited = [False]
_count = [0]


PLACES = int(os.environ.get("PLACES", "5"))
PER_PLACE = int(os.environ.get("PER_PLACE", "10"))


def place_of(n: int) -> int:
    """n 回目（1 始まり、データセット全体の通し）を置く場所。場所 1 を PER_PLACE 回 → 場所 2 … の順"""
    return min((n - 1) // PER_PLACE + 1, PLACES)


def _log_phase(name: str) -> None:
    with open(os.environ.get("KEY_LOG", os.devnull), "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} --- {name} start\n")


def banner(title: str, body: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n  {title}\n    {body}\n{bar}\n", flush=True)


def record_loop(*args, **kwargs):
    dataset, events = kwargs.get("dataset"), kwargs.get("events")
    if dataset is not None and events is not None and not _waited[0]:
        # 最初の 1 本の前に「準備」の区間を入れる（腕は付いてくるが保存しない）。Enter で 1 本目の録画が始まる
        _waited[0] = True
        banner("□ 準備中（保存されません）", "耳栓を置き、腕を開始姿勢にしたら Enter → 1 回目の録画が始まる")
        prep = {k: v for k, v in kwargs.items()
                if k not in ("dataset", "policy", "preprocessor", "postprocessor", "display_compressed_images")}
        prep["control_time_s"] = 3600
        _log_phase("prep")
        events["exit_early"] = False
        _record_loop(**prep)
        if events["stop_recording"]:
            return
    # 始まる前（前の 1 本の保存中など）に押された Enter は捨てる。持ち越すと、この区間が 0 秒で終わる
    if events is not None:
        events["exit_early"] = False
    _log_phase("record" if dataset is not None else "reset")
    if dataset is not None:
        n = getattr(dataset, "num_episodes", _count[0]) + 1  # 保存済みの本数 + 1（録り直しでも数がずれない）
        _count[0] = n
        banner(f"▶ 録画中（{n} 回目・場所 {place_of(n)}）", "つまむ → テープの中心へ入れる → 腕を開始姿勢に戻す → Enter")
    else:
        nxt = _count[0] + 1
        banner(f"■ 置き直し（保存されません）  次は {nxt} 回目・場所 {place_of(nxt)}",
               f"耳栓をテープから取り出して 場所 {place_of(nxt)} に置く → Enter → 次の録画が始まる")
    _record_loop(*args, **kwargs)
    if dataset is not None and events is not None and dataset.episode_buffer is not None \
            and dataset.episode_buffer["size"] == 0 and not events["stop_recording"]:
        print("この 1 本は 0 フレームで終わったので、録り直しにします", flush=True)
        events["rerecord_episode"] = True


rec.init_keyboard_listener = init_keyboard_listener
rec.record_loop = record_loop

if __name__ == "__main__":
    rec.main()
