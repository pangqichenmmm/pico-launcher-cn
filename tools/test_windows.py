"""Compile and run the actual text renderer with the installed MSVC compiler."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import struct

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--black2-rom", type=Path)
args = parser.parse_args()
vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
installation = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires",
    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
vcvars = Path(installation) / "VC/Auxiliary/Build/vcvars64.bat"
folder = ROOT / ".cache/host-tests"
folder.mkdir(parents=True, exist_ok=True)
environment_script = folder / "vc-env.cmd"
environment_script.write_text(f'@echo off\nchcp 65001 >nul\ncall "{vcvars}" >nul\nif errorlevel 1 exit /b 1\nset\n', encoding="utf-8")
output = subprocess.check_output(["cmd", "/d", "/c", str(environment_script)],
                                 text=True, encoding="utf-8", errors="replace")
env = dict(os.environ)
for line in output.splitlines():
    if "=" in line and not line.startswith("="):
        key, value = line.split("=", 1)
        env[key.upper()] = value
compiler = shutil.which("cl", path=env.get("PATH", ""))
if compiler is None:
    raise SystemExit("MSVC environment did not expose the C++ compiler")
command = [compiler, "/nologo", "/std:c++20", "/EHsc", "/utf-8", "/W3",
    "/I" + str(ROOT / "tests/host"), "/I" + str(ROOT / "arm9/source"),
    str(ROOT / "tests/host/font_and_banner_tests.cpp"),
    str(ROOT / "arm9/source/gui/font/nitroFont2.cpp"),
    str(ROOT / "arm9/source/core/StringUtil.cpp"), "/Fe:" + str(folder / "font-tests.exe")]
subprocess.run(command, env=env, cwd=folder, check=True)
run = [str(folder / "font-tests.exe"), str(ROOT)]
if args.black2_rom:
    with args.black2_rom.open("rb") as rom:
        header = rom.read(0x70)
        if header[12:16] != b"IREJ":
            raise SystemExit("The integration fixture expects Japanese Black 2 (IREJ)")
        rom.seek(struct.unpack_from("<I", header, 0x68)[0])
        banner = rom.read(0x23C0)
    fixture = folder / "black2.banner.bin"
    fixture.write_bytes(banner)
    run.append(str(fixture))
result = subprocess.run(run, env=env, cwd=folder, capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
(folder / "native-tests.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
print(result.stdout, end="")
if result.stderr:
    print(result.stderr, end="")
result.check_returncode()
