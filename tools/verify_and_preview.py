"""Validate shipped binaries/assets and compose previews from the C++ renderer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import re
from package_cn import RELEASE, binary_path

from PIL import Image, ImageDraw, ImageFont
from build_chinese_fonts import ROOT, SOURCE, charset


def crc16(data: bytes, value: int = 0xFFFF) -> int:
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xA001 if value & 1 else 0)
    return value


def verify_font(path: Path) -> dict:
    data = path.read_bytes()
    signature, glyphs, maps, masks, ascent, descent, count = struct.unpack_from("<IIIIBBH", data)
    assert signature == 0x3254464E and glyphs == 20
    assert glyphs + count * 8 == maps and maps < masks <= len(data)
    lookup = {}
    offset = maps
    previous_end = -1
    ranges = 0
    while True:
        length, start = struct.unpack_from("<HH", data, offset)
        offset += 4
        if length == 0:
            break
        assert start > previous_end and start + length <= 0x10000
        indices = struct.unpack_from("<" + "H" * length, data, offset)
        assert all(index < count for index in indices)
        lookup.update(zip(range(start, start + length), indices))
        previous_end = start + length - 1
        offset += 2 * length
        ranges += 1
    assert offset == masks
    visible = 0
    for index in range(count):
        packed, left, right, height, top = struct.unpack_from("<IbbBb", data, glyphs + index * 8)
        width, start = packed >> 24, packed & 0xFFFFFF
        end = masks + start + ((width + 1) // 2) * height
        assert end <= len(data) and 0 <= top <= ascent + descent
        assert top + height <= ascent + descent
        visible += width > 0 and height > 0
    points = charset()
    assert all(lookup.get(point, 0) != 0 for point in points)
    for point in points:
        if 0x4E00 <= point <= 0x9FFF:
            index = lookup[point]
            packed, left, right, height, top = struct.unpack_from("<IbbBb", data, glyphs + index * 8)
            assert packed >> 24 > 0 and height > 0
    return {"bytes": len(data), "glyphs": count, "mapped_required_characters": len(points),
            "chinese_ideographs": sum(0x4E00 <= point <= 0x9FFF for point in points),
            "lookup_ranges": ranges, "visible_glyphs": visible,
            "sha256": hashlib.sha256(data).hexdigest()}


if __name__ == "__main__":
    results = {"version": "0.1.1-filename-test", "title_source": "filename", "fonts": {}}
    for name in ["PicoCN-Small", "PicoCN-Regular"]:
        results["fonts"][name] = verify_font(ROOT / "arm9/data" / (name + ".nft2"))
    upstream = json.loads((ROOT / "fonts/upstream-fonts.json").read_text(encoding="utf-8"))
    for filename, expected in upstream["sha256"].items():
        actual = hashlib.sha256((ROOT / "arm9/data" / filename).read_bytes()).hexdigest()
        assert actual == expected, "Upstream font asset was modified"
    nds = binary_path().read_bytes()
    assert crc16(nds[:0x15E]) == struct.unpack_from("<H", nds, 0x15E)[0]
    assert crc16(nds[0xC0:0x15C]) == struct.unpack_from("<H", nds, 0x15C)[0]
    banner_offset = struct.unpack_from("<I", nds, 0x68)[0]
    banner = nds[banner_offset:banner_offset + 0x840]
    assert len(banner) == 0x840 and crc16(banner[0x20:]) == struct.unpack_from("<H", banner, 2)[0]
    assert nds[0x12] == 2
    baseline = ROOT / ".cache/baseline/LAUNCHER.nds"
    baseline_bytes = baseline.stat().st_size if baseline.exists() else upstream["baseline_binary_bytes"]
    results["binary"] = {"bytes": len(nds), "baseline_bytes": baseline_bytes,
                         "added_bytes": len(nds) - baseline_bytes, "unit_code": nds[0x12],
                         "header_crc": "PASS", "logo_crc": "PASS", "banner_crc": "PASS",
                         "sha256": hashlib.sha256(nds).hexdigest()}
    results["hardware_status"] = "Not run on physical consoles; NDS/Lite, DSi and 3DS/2DS validation remains pending."
    link_map = ROOT / "build/arm9.map"
    if link_map.exists():
        content = link_map.read_text(encoding="utf-8", errors="replace")
        end = int(re.search(r"0x([0-9a-f]+)\s+__end__\s*=", content).group(1), 16)
        limit = int(re.search(r"0x([0-9a-f]+)\s+__eheap_end\s*=", content).group(1), 16)
        results["memory"] = {
            "ds_heap_pool_estimate_bytes": ((limit - 0x4000) & ~31) - ((end + 31) & ~31),
            "basis": "DS linker window with existing 0x4000 reserve, before TLSF metadata and runtime allocations; not physical hardware measurement",
        }
    else:
        saved_report = RELEASE / "validation.json"
        if saved_report.exists():
            previous = json.loads(saved_report.read_text(encoding="utf-8"))
            if previous.get("binary", {}).get("sha256") == results["binary"]["sha256"] and "memory" in previous:
                results["memory"] = previous["memory"]
    RELEASE.mkdir(parents=True, exist_ok=True)
    (RELEASE / "validation.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    preview_inputs = ROOT / ".cache/host-tests/renders"
    if not SOURCE.exists() or not preview_inputs.exists():
        print(json.dumps(results, ensure_ascii=False, indent=2))
        print("Existing previews are in docs/previews/. Regenerating them needs the source font and host-test output.")
        raise SystemExit(0)
    previews = ROOT / "docs/previews"
    previews.mkdir(parents=True, exist_ok=True)
    rows = [("常规文字 · 10", "NotoSansJP-Regular-10.nft2.pgm"),
            ("列表标题 · 10", "NotoSansJP-Medium-10.nft2.pgm"),
            ("上屏标题 · 11", "NotoSansJP-Medium-11.nft2.pgm"),
            ("文件名小字 · 7.5", "NotoSansJP-Medium-7_5.nft2.pgm"),
            ("长文件名与省略显示", "filename.pgm")]
    canvas = Image.new("RGB", (880, 610), "#f5f6f7")
    draw = ImageDraw.Draw(canvas)
    heading = ImageFont.truetype(str(SOURCE), 24)
    label = ImageFont.truetype(str(SOURCE), 16)
    draw.text((36, 24), "Pico Launcher CN · 中文显示测试", font=heading, fill="#17262c")
    draw.text((36, 62), "以下文字来自实际 C++ 绘制输出，按 3 倍最近邻放大；非真机截图。", font=label, fill="#526169")
    for i, (description, filename) in enumerate(rows):
        y = 104 + i * 94
        draw.text((36, y), description, font=label, fill="#526169")
        strip = Image.open(ROOT / ".cache/host-tests/renders" / filename).convert("RGB")
        strip = strip.resize((768, 48), Image.Resampling.NEAREST)
        canvas.paste(strip, (36, y + 27))
    canvas.save(previews / "Chinese-render-preview.png")
    filename_canvas = Image.new("RGB", (880, 420), "#f5f6f7")
    draw = ImageDraw.Draw(filename_canvas)
    draw.text((36, 24), "Pico Launcher CN · 文件名显示版", font=heading, fill="#17262c")
    draw.text((36, 62), "实际文字绘制示例，按 3 倍最近邻放大；非真机截图。", font=label, fill="#526169")
    filename_rows = [
        ("这份 ROM 内原有的日文 banner 标题", "goldensun-banner.pgm", 152),
        ("新版列表：文件名（选中后会滚动显示后半段）", "goldensun-filename.pgm", 152),
        ("上屏底部：文件名（沿用滚动显示）", "goldensun-filename-small.pgm", 220),
    ]
    for i, (description, filename, viewport) in enumerate(filename_rows):
        y = 104 + i * 98
        draw.text((36, y), description, font=label, fill="#526169")
        strip = Image.open(ROOT / ".cache/host-tests/renders" / filename).convert("RGB")
        strip = strip.crop((0, 0, viewport, 16)).resize((viewport * 3, 48), Image.Resampling.NEAREST)
        filename_canvas.paste(strip, (36, y + 27))
    filename_canvas.save(previews / "Filename-render-preview.png")
    print(json.dumps(results, ensure_ascii=False, indent=2))
