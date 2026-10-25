"""Build with the project-local native toolchain and an existing Git Bash."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def environment() -> tuple[dict[str, str], Path, Path]:
    git = Path(shutil.which("git") or "")
    candidates = [parent / "usr/bin/sh.exe" for parent in git.parents]
    shell = next((path for path in candidates if path.is_file()), None)
    if shell is None:
        raise SystemExit("Git for Windows with Git Bash is required")
    toolroot = ROOT / ".tools/root"
    wonderful = toolroot
    sdk = wonderful / "thirdparty/blocksds/core"
    if not sdk.is_dir():
        raise SystemExit("Run python tools/bootstrap_windows.py first")
    paths = [toolroot / "ucrt64/bin", wonderful / "bin", wonderful / "lib/native",
             wonderful / "toolchain/gcc-arm-none-eabi/bin", shell.parent,
             shell.parents[2] / "mingw64/bin"]
    env = dict(os.environ)
    env.update(WONDERFUL_TOOLCHAIN=wonderful.as_posix(), BLOCKSDS=sdk.as_posix(),
               BLOCKSDSEXT=(sdk.parent / "external").as_posix(),
               LIBTWL=(ROOT / "libs/libtwl").as_posix())
    env["PATH"] = os.pathsep.join(str(path) for path in paths) + os.pathsep + env["PATH"]
    return env, toolroot / "ucrt64/bin/make.exe", shell


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    env, make, shell = environment()
    label = "baseline" if args.baseline else "cn"
    folder = ROOT / ".cache/logs"
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / ("build-" + label + ".log")
    print(f"Building {label}; complete log: {log}", flush=True)
    command = [str(make), f"-j{args.jobs}", "SHELL=" + shell.as_posix()]
    with log.open("w", encoding="utf-8") as output:
        result = subprocess.run(command, cwd=ROOT, env=env,
                                stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-35:]))
        sys.exit(result.returncode)
    if args.baseline:
        destination = ROOT / ".cache/baseline"
        destination.mkdir(parents=True, exist_ok=True)
        for name in ["LAUNCHER.nds", "build/arm9.elf", "build/arm9.map"]:
            shutil.copy2(ROOT / name, destination / Path(name).name)
    print(f"Build succeeded: {(ROOT / 'LAUNCHER.nds').stat().st_size:,} bytes", flush=True)
