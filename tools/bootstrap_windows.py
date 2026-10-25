"""Prepare a relocatable native Windows BlocksDS toolchain inside .tools/."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile

from fetch_build_inputs import ROOT, download

REPOS = {
    "wonderful": "https://wonderful.asie.pl/packages/rolling/windows/x86_64/",
    "blocksds": "https://blocksds.skylyrac.net/packages/rolling/windows/x86_64/",
    "ucrt64": "https://repo.msys2.org/mingw/ucrt64/",
}
DESTINATION = ROOT / ".tools" / "root"
LOCK = ROOT / "tools" / "toolchain-windows.lock.json"


def fields(text: str) -> dict[str, list[str]]:
    return {lines[0].strip("%"): lines[1:]
            for block in text.strip().split("\n\n")
            if (lines := block.splitlines())}


def database(name: str) -> dict[str, dict]:
    path = download(name + ".db", REPOS[name] + name + ".db")
    records = []
    try:
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                if member.name.endswith("/desc"):
                    records.append(archive.extractfile(member).read().decode())
    except tarfile.ReadError:
        # Windows' bundled libarchive also reads MSYS2's Zstandard databases.
        folder = ROOT / ".cache" / "databases" / name
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xf", str(path), "-C", str(folder)], check=True)
        records = [item.read_text(encoding="utf-8") for item in folder.glob("*/desc")]
    result = {}
    for record in records:
        values = fields(record)
        package = values["NAME"][0]
        result[package] = {
            "name": package,
            "url": REPOS[name] + values["FILENAME"][0],
            "sha256": values["SHA256SUM"][0],
            "bytes": int(values["CSIZE"][0]),
            "dependencies": values.get("DEPENDS", []),
        }
    return result


def lock_packages() -> list[dict]:
    if LOCK.exists():
        return json.loads(LOCK.read_text(encoding="utf-8"))["packages"]
    packages = {}
    for name in REPOS:
        packages.update(database(name))
    selected = {}

    def include(name: str) -> None:
        name = re.split(r"[<>=]", name)[0]
        if name in selected:
            return
        if name not in packages:
            raise RuntimeError(f"Unresolved native toolchain dependency: {name}")
        selected[name] = packages[name]
        for dependency in packages[name]["dependencies"]:
            include(dependency)

    include("blocksds-toolchain")
    include("mingw-w64-ucrt-x86_64-make")
    result = sorted(selected.values(), key=lambda value: value["name"])
    LOCK.write_text(json.dumps({"packages": result}, indent=2) + "\n", encoding="utf-8")
    return result


def checked_download(package: dict) -> tuple[dict, Path]:
    filename = package["url"].rsplit("/", 1)[1]
    target = download(filename, package["url"])
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != package["sha256"]:
        raise RuntimeError(f"SHA256 mismatch for {filename}")
    return package, target


def unpack(path: Path) -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".zst":
        listing = subprocess.run(["tar", "-tf", str(path)], check=True,
                                 capture_output=True, text=True).stdout
        for name in listing.splitlines():
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                raise RuntimeError(f"Unsafe package member: {name}")
        subprocess.run(["tar", "-xf", str(path), "-C", str(DESTINATION)], check=True)
        return
    root = DESTINATION.resolve()
    pending_links = []
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            destination = (root / member.name).resolve()
            if not destination.is_relative_to(root):
                raise RuntimeError(f"Unsafe package member: {member.name}")
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
            elif member.issym() or member.islnk():
                target = ((destination.parent if member.issym() else root) / member.linkname).resolve()
                if not target.is_relative_to(root):
                    raise RuntimeError(f"Unsafe package link: {member.name}")
                pending_links.append((destination, target))
        for _ in range(8):
            remaining = []
            for destination, target in pending_links:
                if not target.exists():
                    remaining.append((destination, target))
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                if target.is_dir():
                    shutil.copytree(target, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(target, destination)
            pending_links = remaining
            if not pending_links:
                break
        if pending_links:
            raise RuntimeError(f"Unresolved package links: {pending_links[:3]}")


if __name__ == "__main__":
    plan = lock_packages()
    print(f"Preparing {len(plan)} verified packages ({sum(item['bytes'] for item in plan) / 1024**2:.1f} MiB downloads)", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for package, archive_path in executor.map(checked_download, plan):
            marker = DESTINATION / (".installed-" + package["name"] + ".sha256")
            if not marker.exists() or marker.read_text() != package["sha256"]:
                unpack(archive_path)
                marker.write_text(package["sha256"])
                print("Extracted " + package["name"], flush=True)
    make = DESTINATION / "ucrt64" / "bin" / "mingw32-make.exe"
    shutil.copy2(make, make.with_name("make.exe"))
    print("Native Windows toolchain ready in .tools/root", flush=True)
