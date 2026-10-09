#!/usr/bin/env python3
"""Fail if tracked files or commit authors leak personal information.

Checks (all tracked files, plus every commit's author and committer):
  1. e-mail addresses other than GitHub/Anthropic-style noreply addresses
  2. lines containing a home-directory path (the Unix home root, or a Windows drive's Users folder)
  3. GPS position in the EXIF data of image files

The patterns are assembled from pieces so that this file does not match itself, and no real name
appears anywhere (the repository is public).
"""

import re
import subprocess
import sys
from pathlib import Path

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
NOREPLY = re.compile(r"(^|[.+@])noreply(@|\.)|@users\.noreply\.github\.com$", re.IGNORECASE)
HOME_UNIX = re.compile("/" + "home" + "/")
HOME_WIN = re.compile(r"[A-Za-z]:[\\/]+" + "Users" + r"[\\/]", re.IGNORECASE)
IMAGE = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}
GPS_TAG = 34853  # EXIF GPSInfo IFD


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    return [Path(p) for p in out.decode().split("\0") if p]


def text_findings(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        for email in EMAIL.findall(line):
            if not NOREPLY.search(email):
                found.append(f"{path}:{n}: e-mail address that is not noreply")
        if HOME_UNIX.search(line) or HOME_WIN.search(line):
            found.append(f"{path}:{n}: home-directory path")
    return found


def gps_findings(path):
    if path.suffix.lower() not in IMAGE:
        return []
    try:
        from PIL import Image
    except ImportError:
        return [f"{path}: Pillow is not installed; cannot check EXIF"]
    try:
        with Image.open(path) as im:
            gps = im.getexif().get_ifd(GPS_TAG)
    except Exception as exc:  # unreadable image: report, do not guess
        return [f"{path}: cannot read EXIF ({type(exc).__name__})"]
    return [f"{path}: EXIF GPS position present"] if gps else []


def author_findings():
    log = subprocess.run(["git", "log", "--format=%ae%n%ce"], capture_output=True, text=True)
    if log.returncode != 0:  # no commit yet (first commit being prepared)
        return []
    out = log.stdout
    bad = sorted({e for e in out.split() if not NOREPLY.search(e)})
    return [f"commit author/committer e-mail is not noreply: {e}" for e in bad]


def main():
    findings = []
    for path in tracked():
        findings += text_findings(path) + gps_findings(path)
    findings += author_findings()
    for f in findings:
        print(f)
    print(f"checked {len(tracked())} tracked files: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
