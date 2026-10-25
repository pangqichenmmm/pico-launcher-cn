"""Build two shared CJK fallback fonts without changing upstream Latin fonts.

Requires Pillow and fontTools. The source font is Noto Sans CJK SC Regular,
licensed under SIL OFL 1.1. Run fetch_build_inputs.py to download its inputs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache/downloads/NotoSansCJKsc-Regular.otf"
SOURCE_SHA256 = "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b"
SIGNATURE = 0x3254464E


def charset() -> list[int]:
    points = {ord("?"), ord(" ")}
    for lead in range(0xA1, 0xF8):
        for trail in range(0xA1, 0xFF):
            try:
                character = bytes([lead, trail]).decode("gb2312")
            except UnicodeDecodeError:
                continue
            points.add(ord(character))
    return sorted(points)


def pack_mask(image: Image.Image) -> bytes:
    result = bytearray()
    for y in range(image.height):
        for x in range(0, image.width, 2):
            low = image.getpixel((x, y))
            high = image.getpixel((x + 1, y)) if x + 1 < image.width else 0
            result.append(low | (high << 4))
    return bytes(result)


def render_glyph(font: ImageFont.FreeTypeFont, codepoint: int, line_height: int):
    character = chr(codepoint)
    advance = round(font.getlength(character))
    box = font.getbbox(character, anchor="ls")
    ink_height = box[3] - box[1]
    while ink_height > line_height:
        font = font.font_variant(size=font.size - 1)
        advance = round(font.getlength(character))
        box = font.getbbox(character, anchor="ls")
        ink_height = box[3] - box[1]
    left = min(0, box[0])
    width = max(advance, box[2]) - left
    canvas = Image.new("L", (max(1, width), line_height))
    baseline = (line_height - ink_height) // 2 - box[1]
    ImageDraw.Draw(canvas).text((-left, baseline), character, font=font, fill=255, anchor="ls")
    canvas = canvas.point([round(value * 15 / 255) for value in range(256)])
    crop = canvas.getbbox()
    if crop is None:
        return (0, 0, advance, 0, 0, b"")
    image = canvas.crop(crop)
    spacing_left = left + crop[0]
    return (image.width, spacing_left, advance - spacing_left - image.width,
            image.height, crop[1], pack_mask(image))


def character_map(mapping: dict[int, int]) -> bytes:
    # A dense CJK interval avoids thousands of linear range lookups on DS CPUs.
    # Uncovered ideographs show '?' instead of silently disappearing.
    complete = dict(mapping)
    for point in range(0x4E00, 0xA000):
        complete.setdefault(point, mapping[ord("?")])
    runs = []
    for point in sorted(complete):
        if not runs or point != runs[-1][0] + len(runs[-1][1]):
            runs.append((point, []))
        runs[-1][1].append(complete[point])
    result = bytearray()
    for start, indices in runs:
        result += struct.pack("<HH", len(indices), start)
        result += struct.pack("<" + "H" * len(indices), *indices)
    return bytes(result) + b"\0\0\0\0"


def build_font(pixels: int, ascend: int, descend: int, points: list[int]) -> tuple[bytes, dict]:
    font = ImageFont.truetype(str(SOURCE), pixels)
    line_height = ascend + descend
    glyphs = [(0, 0, max(1, pixels // 2), 0, 0, b"")]
    mapping = {}
    for point in points:
        mapping[point] = len(glyphs)
        glyphs.append(render_glyph(font, point, line_height))
    masks = bytearray()
    table = bytearray()
    for width, left, right, height, top, mask in glyphs:
        if len(masks) >= 1 << 24:
            raise ValueError("NFT2 glyph mask offset overflow")
        table += struct.pack("<IbbBb", len(masks) | width << 24, left, right, height, top)
        masks += mask
    charmap = character_map(mapping)
    glyph_offset = 20
    map_offset = glyph_offset + len(table)
    data_offset = map_offset + len(charmap)
    header = struct.pack("<IIIIBBH", SIGNATURE, glyph_offset, map_offset,
                         data_offset, ascend, descend, len(glyphs))
    blob = header + table + charmap + masks
    return blob, {"pixels": pixels, "ascend": ascend, "descend": descend,
                  "glyphs": len(glyphs), "mapped_characters": len(points),
                  "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


if __name__ == "__main__":
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise SystemExit("The source font differs from the reviewed build input")
    points = charset()
    source_font = TTFont(SOURCE)
    covered = source_font.getBestCmap()
    absent = [point for point in points if point not in covered]
    if absent:
        raise SystemExit(f"Source font is missing {len(absent)} required characters")
    report = {"source_sha256": SOURCE_SHA256, "fonts": {}}
    for name, pixels, ascend, descend in [("PicoCN-Small", 9, 8, 2),
                                          ("PicoCN-Regular", 12, 11, 2)]:
        blob, info = build_font(pixels, ascend, descend, points)
        (ROOT / "arm9/data" / (name + ".nft2")).write_bytes(blob)
        report["fonts"][name] = info
        print(f"{name}: {info['bytes']:,} bytes; {info['mapped_characters']} characters", flush=True)
    notices = ROOT / "fonts"
    notices.mkdir(exist_ok=True)
    (notices / "OFL-1.1.txt").write_bytes((ROOT / ".cache/downloads/NotoCJK-OFL.txt").read_bytes())
    copyrights = sorted({record.toUnicode() for record in source_font["name"].names if record.nameID == 0})
    (notices / "NOTICE.txt").write_text(
        "PicoCN shared CJK fallback fonts\n\n"
        "Derived from Noto Sans CJK SC Regular under SIL OFL 1.1.\n"
        "Source: https://github.com/notofonts/noto-cjk\n"
        + "\n".join(copyrights)
        + "\n\nModified for Pico Launcher CN: subset to GB2312 characters, rasterized\n"
          "at 9/12 pixels, and converted to NFT2. These are modified fonts named\n"
          "PicoCN; they are not original or unmodified Noto font releases.\n",
        encoding="utf-8")
    (notices / "build-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
