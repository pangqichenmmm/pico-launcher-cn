"""Prepare directly usable NDS files; do not create installation/source ZIPs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.1-filename-test"
RELEASE = ROOT / "releases" / VERSION


def binary_path() -> Path:
    built = ROOT / "LAUNCHER.nds"
    return built if built.is_file() else RELEASE / "_picoboot.nds"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    source = binary_path()
    report_path = RELEASE / "validation.json"
    if not report_path.exists():
        raise SystemExit("Run python tools/verify_and_preview.py before preparing the release")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if sha(source) != report["binary"]["sha256"]:
        raise SystemExit("The compiled binary differs from validation.json; run verification again")
    RELEASE.mkdir(parents=True, exist_ok=True)
    destination = RELEASE / "_picoboot.nds"
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    tests = ROOT / ".cache/host-tests/native-tests.txt"
    if tests.exists():
        shutil.copy2(tests, RELEASE / "native-tests.txt")
    for source_name, output_name in [
        ("INSTALL-CN.txt", "INSTALL-CN.txt"),
        ("LICENSE.txt", "LICENSE.txt"),
        ("fonts/OFL-1.1.txt", "FONT-OFL-1.1.txt"),
        ("fonts/NOTICE.txt", "FONT-NOTICE.txt"),
    ]:
        shutil.copy2(ROOT / source_name, RELEASE / output_name)
    notices = []
    notice_paths = sorted((ROOT / "licenses").glob("*.txt"))
    notice_paths += sorted((ROOT / "libs/libtwl").glob("LICENSE*"))
    for path in notice_paths:
        notices.append(path.relative_to(ROOT).as_posix() + "\n" + "=" * 72 + "\n"
                       + path.read_text(encoding="utf-8") + "\n")
    (RELEASE / "THIRD-PARTY-LICENSES.txt").write_text("\n".join(notices), encoding="utf-8")
    (RELEASE / "SHA256SUMS.txt").write_text(sha(destination) + "  _picoboot.nds\n", encoding="utf-8")
    binaries = sorted((ROOT / "releases").glob("*/_picoboot.nds"))
    sums = "".join(sha(path) + "  " + path.relative_to(ROOT / "releases").as_posix() + "\n"
                   for path in binaries)
    (ROOT / "releases/SHA256SUMS.txt").write_text(sums, encoding="utf-8")
    print(f"Ready to copy: {destination}")
    print(f"{destination.stat().st_size:,} bytes; sha256={sha(destination)}")
