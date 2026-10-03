"""Demo content drawn with Pillow, so the repository ships no binary samples."""

import csv
import io
import math
import random
import struct
import wave
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PALETTES = [
    ["#0b3954", "#087e8b", "#bfd7ea", "#ff5a5f", "#c81d25"],
    ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"],
    ["#22223b", "#4a4e69", "#9a8c98", "#c9ada7", "#f2e9e4"],
    ["#1d3557", "#457b9d", "#a8dadc", "#f1faee", "#e63946"],
    ["#283618", "#606c38", "#fefae0", "#dda15e", "#bc6c25"],
    ["#03045e", "#0077b6", "#00b4d8", "#90e0ef", "#caf0f8"],
    ["#3d405b", "#81b29a", "#f2cc8f", "#e07a5f", "#f4f1de"],
    ["#10002b", "#3c096c", "#7b2cbf", "#c77dff", "#e0aaff"],
]


@dataclass
class DemoFile:
    category: str
    title: str
    name: str
    description: str
    make: Callable[[random.Random], bytes]


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def _gradient(size, top, bottom) -> Image.Image:
    height = size[1]
    column = Image.new("RGB", (1, height))
    for y in range(height):
        column.putpixel((0, y), _mix(top, bottom, y / (height - 1)))
    return column.resize(size)


def _jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=88, optimize=True)
    return buffer.getvalue()


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def landscape(palette: list[str]) -> Callable[[random.Random], bytes]:
    def make(rng: random.Random) -> bytes:
        size = (1600, 1100)
        colors = [_rgb(c) for c in palette]
        image = _gradient(size, colors[2], _mix(colors[4], (255, 255, 255), 0.35))
        draw = ImageDraw.Draw(image)
        sun = (rng.randint(300, 1300), rng.randint(220, 420))
        radius = rng.randint(70, 120)
        draw.ellipse(
            [sun[0] - radius, sun[1] - radius, sun[0] + radius, sun[1] + radius],
            fill=_mix(colors[3], (255, 255, 255), 0.3),
        )
        layers = 5
        for layer in range(layers):
            base = 520 + layer * 115
            amplitude = 170 - layer * 25
            phase = rng.random() * math.tau
            points = [(0, size[1])]
            for x in range(0, size[0] + 40, 40):
                y = (
                    base
                    - amplitude
                    * (
                        0.6 * math.sin(x / (260 + layer * 40) + phase)
                        + 0.4 * math.sin(x / 97 + phase * 2)
                    )
                    + rng.randint(-12, 12)
                )
                points.append((x, y))
            points.append((size[0], size[1]))
            shade = _mix(colors[1], colors[0], layer / (layers - 1))
            draw.polygon(points, fill=_mix(shade, colors[2], 0.45 * (1 - layer / layers)))
        return _jpeg(image.filter(ImageFilter.SMOOTH))

    return make


def poster(palette: list[str]) -> Callable[[random.Random], bytes]:
    def make(rng: random.Random) -> bytes:
        cell, cols, rows = 200, 6, 8
        image = Image.new("RGB", (cell * cols, cell * rows), _rgb(palette[-1]))
        draw = ImageDraw.Draw(image)
        colors = [_rgb(c) for c in palette[:-1]]
        for row in range(rows):
            for col in range(cols):
                x, y = col * cell, row * cell
                box = [x, y, x + cell, y + cell]
                background, shape = rng.sample(colors, 2)
                draw.rectangle(box, fill=background)
                match rng.randrange(5):
                    case 0:
                        draw.ellipse(box, fill=shape)
                    case 1:
                        start = rng.choice([0, 90, 180, 270])
                        corner = rng.choice(
                            [(x - cell, y - cell), (x, y - cell), (x - cell, y), (x, y)]
                        )
                        draw.pieslice(
                            [corner[0], corner[1], corner[0] + 2 * cell, corner[1] + 2 * cell],
                            start,
                            start + 90,
                            fill=shape,
                        )
                    case 2:
                        draw.polygon(
                            [(x, y + cell), (x + cell, y + cell), (x + cell, y)], fill=shape
                        )
                    case 3:
                        inset = cell // 4
                        draw.ellipse(
                            [x + inset, y + inset, x + cell - inset, y + cell - inset], fill=shape
                        )
                    case _:
                        draw.rectangle([x, y + cell // 2, x + cell, y + cell], fill=shape)
        return _png(image.quantize(colors=16).convert("RGB"))

    return make


def waves(palette: list[str]) -> Callable[[random.Random], bytes]:
    def make(rng: random.Random) -> bytes:
        size = (1400, 1050)
        colors = [_rgb(c) for c in palette]
        image = Image.new("RGB", size, colors[0])
        draw = ImageDraw.Draw(image)
        lines = 34
        for i in range(lines):
            t = i / (lines - 1)
            color = _mix(colors[1 + int(t * 3)], colors[2 + int(t * 2)], (t * 3) % 1)
            phase, frequency = rng.random() * math.tau, 0.004 + rng.random() * 0.004
            points = [
                (x, 60 + i * 28 + 60 * math.sin(x * frequency + phase + i * 0.18))
                for x in range(-20, size[0] + 20, 10)
            ]
            draw.line(points, fill=color, width=9, joint="curve")
        return _jpeg(image)

    return make


def document_pdf(title: str, paragraphs: list[str]) -> Callable[[random.Random], bytes]:
    def make(rng: random.Random) -> bytes:
        page = Image.new("RGB", (1240, 1754), "white")
        draw = ImageDraw.Draw(page)
        heading, body = ImageFont.load_default(56), ImageFont.load_default(30)
        draw.text((110, 140), title, font=heading, fill="#111827")
        draw.line([(110, 230), (1130, 230)], fill="#d1d5db", width=3)
        y = 290
        for paragraph in paragraphs:
            line = ""
            for word in paragraph.split():
                candidate = f"{line} {word}".strip()
                if draw.textlength(candidate, font=body) > 1020:
                    draw.text((110, y), line, font=body, fill="#374151")
                    y, line = y + 46, word
                else:
                    line = candidate
            draw.text((110, y), line, font=body, fill="#374151")
            y += 80
        buffer = io.BytesIO()
        page.save(buffer, "PDF", resolution=150)
        return buffer.getvalue()

    return make


def text_file(text: str) -> Callable[[random.Random], bytes]:
    return lambda rng: text.encode()


def loans_csv(rng: random.Random) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["month", "visitors", "loans", "returns", "new_readers"])
    for month in range(1, 13):
        visitors = rng.randint(1800, 3400)
        loans = int(visitors * rng.uniform(0.5, 0.7))
        writer.writerow(
            [f"2025-{month:02d}", visitors, loans, loans - rng.randint(0, 80), rng.randint(40, 160)]
        )
    return buffer.getvalue().encode()


def chime_wav(rng: random.Random) -> bytes:
    rate, seconds = 22050, 3
    notes = [523.25, 659.25, 783.99, 1046.5]
    frames = bytearray()
    for n in range(rate * seconds):
        t = n / rate
        note = notes[min(int(t / 0.75), 3)]
        envelope = math.exp(-3 * (t % 0.75))
        frames += struct.pack("<h", int(12000 * envelope * math.sin(math.tau * note * t)))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(bytes(frames))
    return buffer.getvalue()


def bundle_zip(rng: random.Random) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for i in range(1, 6):
            archive.writestr(
                f"scans/page-{i:02d}.txt", f"Page {i}\n" + "Lorem ipsum dolor sit amet. " * 40
            )
    return buffer.getvalue()


CATEGORIES = {
    "Landscapes": "Generated mountain views used on the reading room screens.",
    "Posters": "Geometric posters for exhibitions and events.",
    "Patterns": "Backgrounds for printed materials.",
    "Documents": "Rules, reports and other paperwork.",
    "Audio": "Sound files for announcements.",
}

LANDSCAPES = [
    ("Morning in the valley", "Soft light over the hills, the first in the series."),
    ("Blue ridge", "Five layers of mountains fading into the haze."),
    ("Evening pass", "Warm sunset behind the northern ridge."),
    ("Quiet highlands", ""),
    ("Lavender peaks", "Made for the poetry evening flyer."),
    ("Coastal range", "Cool tones, works well behind white text."),
    ("Autumn slopes", ""),
    ("Northern lights hills", "Violet sky over dark slopes."),
]
POSTERS = [
    ("Bauhaus week", "Poster for the design history week."),
    ("Shapes and colours", "Children's workshop announcement."),
    ("Modernism talk", ""),
    ("Grid study no. 4", "Twelve by sixteen grid, quantised to sixteen colours."),
    ("Summer reading", "Main poster of the summer reading programme."),
    ("Open archive day", ""),
    ("Print club", "Monthly meeting of the risograph club."),
    ("Colour theory", ""),
]
PATTERNS = [
    ("Ocean lines", "Wave pattern for bookmarks."),
    ("Sand dunes", ""),
    ("Night current", "Dark background for the event programme."),
    ("Spring wind", ""),
    ("Deep water", "Used on the back of the membership card."),
    ("Violet field", ""),
]


def demo_files() -> Iterator[DemoFile]:
    for i, (title, description) in enumerate(LANDSCAPES):
        yield DemoFile(
            "Landscapes",
            title,
            f"landscape-{i + 1:02d}.jpg",
            description,
            landscape(PALETTES[i % len(PALETTES)]),
        )
    for i, (title, description) in enumerate(POSTERS):
        yield DemoFile(
            "Posters",
            title,
            f"poster-{i + 1:02d}.png",
            description,
            poster(PALETTES[(i + 3) % len(PALETTES)]),
        )
    for i, (title, description) in enumerate(PATTERNS):
        yield DemoFile(
            "Patterns",
            title,
            f"pattern-{i + 1:02d}.jpg",
            description,
            waves(PALETTES[(i + 5) % len(PALETTES)]),
        )
    yield DemoFile(
        "Documents",
        "Reading room rules",
        "reading-room-rules.pdf",
        "One page, printed at the entrance.",
        document_pdf(
            "Reading room rules",
            [
                "The reading room is open from 9 to 21 on weekdays and from 10 to 18 on weekends.",
                "Rare books are issued against a library card and stay in the room.",
                "Laptops and tablets are welcome. Please keep phones on silent.",
                "Scanning is free for personal use. Ask the librarian for the archive scanner.",
            ],
        ),
    )
    yield DemoFile(
        "Documents",
        "Annual report 2025",
        "annual-report-2025.pdf",
        "Summary of the year for the board.",
        document_pdf(
            "Annual report 2025",
            [
                "The library served 31 thousand visitors and issued 19 thousand loans.",
                "The digital archive grew by four thousand scans of local newspapers.",
                "Next year the reading room gets new lighting and twelve more seats.",
            ],
        ),
    )
    yield DemoFile(
        "Documents",
        "Loans by month",
        "loans-2025.csv",
        "Visitors, loans and returns for each month of 2025.",
        loans_csv,
    )
    yield DemoFile(
        "Documents",
        "Cataloguing notes",
        "cataloguing-notes.md",
        "How to name and describe new files.",
        text_file(
            "# Cataloguing notes\n\n"
            "- Title in sentence case, no file extension.\n"
            "- One category per file.\n"
            "- Mention the source and the year in the description.\n"
        ),
    )
    yield DemoFile(
        "Documents",
        "Newspaper scans 1962",
        "newspaper-scans-1962.zip",
        "Five pages of the local weekly, plain text extracted.",
        bundle_zip,
    )
    yield DemoFile(
        "Audio",
        "Closing time chime",
        "closing-chime.wav",
        "Played fifteen minutes before closing.",
        chime_wav,
    )


def build(item: DemoFile, seed: int) -> ContentFile:
    return ContentFile(item.make(random.Random(seed)), name=item.name)  # noqa: S311
