"""Download public build inputs into this checkout; never install system tools."""
from __future__ import annotations

import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "NotoSansCJKsc-Regular.otf": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    "NotoCJK-OFL.txt": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE",
}


def download(name: str, url: str) -> Path:
    folder = ROOT / ".cache" / "downloads"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if not target.exists():
        pending = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(url, timeout=90) as response, pending.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        pending.replace(target)
    print(f"{name}: {target.stat().st_size:,} bytes; sha256={hashlib.sha256(target.read_bytes()).hexdigest()}", flush=True)
    return target


if __name__ == "__main__":
    for filename, source_url in INPUTS.items():
        download(filename, source_url)
