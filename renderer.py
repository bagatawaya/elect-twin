#!/usr/bin/env python3
"""OpenZoo Procedural SVG Studio v2: deterministic art at zero API cost.

CLI contract:
    python3 renderer.py OUTPUT_DIRECTORY < spec.json

The input is at most 8192 bytes. The renderer writes <sha256>.svg and
<sha256>.json with O_NOFOLLOW, O_EXCL and mode 0600, then prints a JSON
receipt. Repeated writes of identical bytes are safe and idempotent.

A v1 spec has exactly agent, title, nodes and palette and renders a flowchart.
A v2 spec adds template and optional remix_of. Template fields:
  flowchart:       nodes: [1..6 strings]
  comic_strip:     panels: [2..3 {stamp, text, caption}]
  trading_card:    symbol, horizon (7D/14D/30D), conviction, entry, target,
                   stop and optional stamp (default chart)
  versus_poster:   left/right: {name, stamp, crowd}
  greentext_meme:  stamp and lines: [1..8 strings]
  infographic:     bars: [1..6 {label, value}] and notes: [1..4 strings]
  pixel_avatar:    pixels: square 8..32 grid of mapped ASCII rows or direct
                   hex-color cells; legend maps single characters to hex colors

Only standard-library modules and fixed vector geometry are used. User text
is ASCII/XML escaped; no scripts, external images, links or foreignObject.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import textwrap
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

MAX_STDIN_BYTES = 8192
STAMPS = ("robot", "bull", "bear", "owl", "crown", "bolt", "chart", "shield")
TEMPLATES = (
    "flowchart", "comic_strip", "trading_card", "versus_poster",
    "greentext_meme", "infographic", "pixel_avatar",
)
PALETTES = {
    "midnight": {"bg": "#0B1020", "panel": "#151E33", "ink": "#F8FAFC", "muted": "#94A3B8", "accent": "#2DD4BF", "accent2": "#A78BFA", "line": "#334155", "danger": "#FB7185"},
    "porcelain": {"bg": "#F7F3EC", "panel": "#FFFDF8", "ink": "#172033", "muted": "#64748B", "accent": "#0F766E", "accent2": "#C2653C", "line": "#D8CFC2", "danger": "#B42318"},
    "terminal": {"bg": "#07110B", "panel": "#0D1D13", "ink": "#D9F99D", "muted": "#86A98F", "accent": "#4ADE80", "accent2": "#FACC15", "line": "#245235", "danger": "#F87171"},
    "ocean": {"bg": "#ECF8FF", "panel": "#FFFFFF", "ink": "#12304A", "muted": "#54758C", "accent": "#0369A1", "accent2": "#0891B2", "line": "#BAE0F2", "danger": "#BE365D"},
    "sunset": {"bg": "#2A1428", "panel": "#3B1D35", "ink": "#FFF7ED", "muted": "#D8B4C8", "accent": "#FB923C", "accent2": "#F472B6", "line": "#6B3455", "danger": "#FDA4AF"},
    "forest": {"bg": "#F1F5EC", "panel": "#FAFCF7", "ink": "#1D3023", "muted": "#617365", "accent": "#3F6212", "accent2": "#A16207", "line": "#CDD9C4", "danger": "#A93636"},
    "candy": {"bg": "#FFF1F8", "panel": "#FFFFFF", "ink": "#4C1D3D", "muted": "#98617F", "accent": "#DB2777", "accent2": "#7C3AED", "line": "#F5C6DE", "danger": "#BE123C"},
    "mono": {"bg": "#F4F4F4", "panel": "#FFFFFF", "ink": "#181818", "muted": "#666666", "accent": "#333333", "accent2": "#777777", "line": "#CCCCCC", "danger": "#555555"},
}
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def escape(value: Any) -> str:
    """Return ASCII-only XML text/attribute content, including quote escaping."""
    text = _xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})
    # Encode '=' as well so hostile text can never reproduce an href= token,
    # even in its inert escaped form. All user-originated bytes stay ASCII.
    text = text.replace("=", "&#61;")
    return text.encode("ascii", "xmlcharrefreplace").decode("ascii")


def _text(value: Any, name: str, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return value


def _string_list(value: Any, name: str, minimum: int, maximum: int, length: int = 180) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name} must contain {minimum}..{maximum} strings")
    return [_text(item, name, length) for item in value]


def _number(value: Any, name: str, minimum: float = -1e12, maximum: float = 1e12) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside its allowed range")
    return float(value)


def _fmt(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _stamp(value: Any) -> str:
    if value not in STAMPS:
        raise ValueError(f"stamp must be one of: {', '.join(STAMPS)}")
    return value


def _keys(spec: dict[str, Any], allowed: set[str]) -> None:
    unknown = set(spec) - allowed
    if unknown:
        raise ValueError(f"unknown spec keys: {', '.join(sorted(unknown))}")


def _common(spec: dict[str, Any]) -> tuple[str, str, dict[str, str]]:
    agent = _text(spec.get("agent"), "agent", 80)
    title = _text(spec.get("title"), "title", 120)
    palette_name = spec.get("palette")
    if not isinstance(palette_name, str) or palette_name not in PALETTES:
        raise ValueError(f"palette must be one of: {', '.join(PALETTES)}")
    remix = spec.get("remix_of")
    if remix is not None and (not isinstance(remix, str) or not _HEX_64.fullmatch(remix)):
        raise ValueError("remix_of must be a lowercase SHA-256 digest")
    return agent, title, PALETTES[palette_name]


def _label(text: Any, x: float, y: float, size: int, color: str,
           weight: int = 400, anchor: str = "start", class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    return (f'<text{class_attr} x="{_fmt(x)}" y="{_fmt(y)}" fill="{color}" '
            f'font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{escape(text)}</text>')


def _wrapped(text: str, x: float, y: float, size: int, color: str, width: int,
             weight: int = 400, line_height: int | None = None,
             class_name: str = "", max_lines: int = 8) -> str:
    lines = textwrap.wrap(text, width=width, break_long_words=True,
                          break_on_hyphens=False) or [""]
    lines = lines[:max_lines]
    step = line_height or round(size * 1.35)
    class_attr = f' class="{class_name}"' if class_name else ""
    spans = "".join(
        f'<tspan x="{_fmt(x)}" dy="{0 if index == 0 else step}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return (f'<text{class_attr} x="{_fmt(x)}" y="{_fmt(y)}" fill="{color}" '
            f'font-family="{FONT}" font-size="{size}" font-weight="{weight}">{spans}</text>')


def _stamp_svg(name: str, x: float, y: float, size: float, color: str) -> str:
    """Compose one fixed 100x100 vector stamp without ids or external assets."""
    shapes = {
        "robot": '''
<path d="M50 8v12M42 8h16" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
<rect x="20" y="22" width="60" height="46" rx="12" fill="none" stroke="currentColor" stroke-width="4"/>
<circle cx="37" cy="43" r="5" fill="currentColor"/><circle cx="63" cy="43" r="5" fill="currentColor"/>
<path d="M36 56h28M15 39H8v18h12M85 39h7v18H80M35 68v18h30V68M28 92h14M58 92h14" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>
''',
        "bull": '''
<path d="M29 29C13 29 9 17 12 9c7 12 18 11 28 13M71 29c16 0 20-12 17-20-7 12-18 11-28 13" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
<path d="M25 34 13 42l17 7M75 34l12 8-17 7" fill="currentColor"/>
<path d="M28 28Q50 15 72 28l5 33-15 27H38L23 61Z" fill="none" stroke="currentColor" stroke-width="4"/>
<circle cx="38" cy="47" r="4" fill="currentColor"/><circle cx="62" cy="47" r="4" fill="currentColor"/>
<ellipse cx="50" cy="70" rx="17" ry="12" fill="none" stroke="currentColor" stroke-width="4"/><circle cx="43" cy="70" r="3" fill="currentColor"/><circle cx="57" cy="70" r="3" fill="currentColor"/>
''',
        "bear": '''
<circle cx="25" cy="25" r="14" fill="currentColor"/><circle cx="75" cy="25" r="14" fill="currentColor"/>
<circle cx="50" cy="52" r="38" fill="none" stroke="currentColor" stroke-width="5"/>
<circle cx="36" cy="45" r="4" fill="currentColor"/><circle cx="64" cy="45" r="4" fill="currentColor"/>
<ellipse cx="50" cy="65" rx="19" ry="15" fill="none" stroke="currentColor" stroke-width="4"/>
<path d="m43 59 7-4 7 4-7 7ZM50 66v7m-9 0q9 8 18 0" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
''',
        "owl": '''
<path d="M18 27 29 9l13 13q8-5 16 0L71 9l11 18v35Q78 91 50 94 22 91 18 62Z" fill="none" stroke="currentColor" stroke-width="4"/>
<circle cx="35" cy="45" r="15" fill="none" stroke="currentColor" stroke-width="4"/><circle cx="65" cy="45" r="15" fill="none" stroke="currentColor" stroke-width="4"/>
<circle cx="35" cy="45" r="5" fill="currentColor"/><circle cx="65" cy="45" r="5" fill="currentColor"/>
<path d="m43 59 7-6 7 6-7 8ZM25 69q12 4 17 18M75 69q-12 4-17 18" fill="currentColor" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
''',
        "crown": '''
<path d="m12 29 22 17 16-31 16 31 22-17-10 51H22Z" fill="none" stroke="currentColor" stroke-width="5" stroke-linejoin="round"/>
<path d="M23 68h54M27 89h46" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
<circle cx="12" cy="25" r="5" fill="currentColor"/><circle cx="50" cy="11" r="5" fill="currentColor"/><circle cx="88" cy="25" r="5" fill="currentColor"/>
''',
        "bolt": '''
<path d="M56 5 18 56h27l-5 39 42-56H55Z" fill="currentColor" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/>
''',
        "chart": '''
<path d="M12 12v76h78" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round"/>
<rect x="23" y="57" width="13" height="23" rx="2" fill="currentColor"/><rect x="45" y="39" width="13" height="41" rx="2" fill="currentColor"/><rect x="67" y="20" width="13" height="60" rx="2" fill="currentColor"/>
<path d="m20 42 20-17 16 7 27-22" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
''',
        "shield": '''
<path d="M50 7 86 20v29q0 32-36 45Q14 81 14 49V20Z" fill="none" stroke="currentColor" stroke-width="5" stroke-linejoin="round"/>
<path d="m29 50 14 14 29-31" fill="none" stroke="currentColor" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
''',
    }
    return (f'<g class="vector-stamp stamp-{name}" transform="translate({_fmt(x)} {_fmt(y)}) '
            f'scale({_fmt(size / 100)})" color="{color}">{shapes[name]}</g>')


def _document(spec: dict[str, Any], template: str, body: str, width: int, height: int) -> str:
    title = escape(spec["title"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}" '
            f'class="svg-studio template-{template}">\n'
            f'<title>{title}</title>\n'
            f'<desc>Deterministic procedural vector artwork. No external assets or network calls.</desc>\n'
            f'{body}\n</svg>\n')


def _footer(agent: str, y: int, width: int, colors: dict[str, str]) -> str:
    return (_label("BY " + agent, 28, y, 12, colors["muted"], 700) +
            _label("LOCAL VECTOR RENDER · $0.00 API COST", width - 28, y, 12,
                   colors["muted"], 700, "end"))


def _flowchart(spec: dict[str, Any]) -> str:
    _keys(spec, {"agent", "title", "nodes", "palette", "template", "remix_of"})
    agent, title, c = _common(spec)
    nodes = _string_list(spec.get("nodes"), "nodes", 1, 6)
    height = 160 + len(nodes) * 110
    parts = [f'<rect width="720" height="{height}" fill="{c["bg"]}"/>',
             f'<rect x="0" y="0" width="720" height="8" fill="{c["accent"]}"/>',
             _label(title, 40, 58, 28, c["ink"], 800),
             _label("DETERMINISTIC FLOW / " + spec.get("template", "flowchart").upper(), 40, 88, 12, c["muted"], 700)]
    for index, node in enumerate(nodes):
        y = 120 + index * 110
        if index:
            parts.append(f'<path d="M360 {y - 20}v14m-6-6 6 6 6-6" fill="none" stroke="{c["accent"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
        parts.extend([
            f'<g class="flow-node"><rect x="100" y="{y}" width="520" height="82" rx="14" fill="{c["panel"]}" stroke="{c["line"]}" stroke-width="2"/>',
            f'<circle cx="134" cy="{y + 41}" r="18" fill="{c["accent"]}"/>',
            _label(str(index + 1), 134, y + 47, 15, c["bg"], 800, "middle"),
            _wrapped(node, 170, y + 37, 19, c["ink"], 35, 700, max_lines=2) + '</g>',
        ])
    parts.append(_footer(agent, height - 18, 720, c))
    return _document(spec, "flowchart", "\n".join(parts), 720, height)


def _comic(spec: dict[str, Any]) -> str:
    _keys(spec, {"agent", "title", "panels", "palette", "template", "remix_of"})
    agent, title, c = _common(spec)
    panels = spec.get("panels")
    if not isinstance(panels, list) or not 2 <= len(panels) <= 3:
        raise ValueError("panels must contain 2..3 panel objects")
    width = 900
    gap = 16
    panel_width = (width - 48 - gap * (len(panels) - 1)) // len(panels)
    parts = [f'<rect width="900" height="500" fill="{c["bg"]}"/>',
             _label(title, 24, 45, 27, c["ink"], 800),
             _label("PROCEDURAL COMIC / VECTOR STAMPS", 24, 70, 12, c["muted"], 700)]
    for index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            raise ValueError("each panel must be an object")
        _keys(panel, {"stamp", "text", "caption"})
        stamp = _stamp(panel.get("stamp"))
        words = _text(panel.get("text"), "panel text", 220)
        caption = _text(panel.get("caption"), "panel caption", 60)
        x = 24 + index * (panel_width + gap)
        bubble_width = panel_width - 28
        parts.extend([
            f'<g class="comic-panel"><rect x="{x}" y="92" width="{panel_width}" height="350" rx="14" fill="{c["panel"]}" stroke="{c["line"]}" stroke-width="2"/>',
            _label(caption.upper(), x + 14, 121, 12, c["accent"], 800, class_name="panel-caption"),
            f'<rect class="speech-bubble" x="{x + 14}" y="140" width="{bubble_width}" height="116" rx="16" fill="{c["bg"]}" stroke="{c["accent"]}" stroke-width="2"/>',
            f'<path d="m{x + 42} 256 10 18 12-18" fill="{c["bg"]}" stroke="{c["accent"]}" stroke-width="2" stroke-linejoin="round"/>',
            _wrapped(words, x + 28, 174, 16, c["ink"], max(15, int(bubble_width / 9)), 600, 23, max_lines=4),
            _stamp_svg(stamp, x + panel_width / 2 - 65, 282, 130, c["accent2"]) + '</g>',
        ])
    parts.append(_footer(agent, 478, width, c))
    return _document(spec, "comic_strip", "\n".join(parts), width, 500)


def _trading(spec: dict[str, Any]) -> str:
    _keys(spec, {"agent", "title", "symbol", "horizon", "conviction", "entry", "target", "stop", "stamp", "palette", "template", "remix_of"})
    agent, title, c = _common(spec)
    horizon = spec.get("horizon")
    if horizon not in ("7D", "14D", "30D"):
        raise ValueError("horizon must be 7D, 14D or 30D")
    symbol = _text(spec.get("symbol"), "symbol", 16).upper()
    conviction = _number(spec.get("conviction"), "conviction", 0, 100)
    entry = _number(spec.get("entry"), "entry")
    target = _number(spec.get("target"), "target")
    stop = _number(spec.get("stop"), "stop")
    stamp = _stamp(spec.get("stamp", "chart"))
    values = [stop, entry, target, entry + (target - entry) * 0.35, target]
    low, high = min(values), max(values)
    span = high - low or 1
    points = " ".join(f'{70 + i * 135},{390 - round((value - low) / span * 105)}' for i, value in enumerate(values))
    parts = [
        '<rect width="720" height="780" rx="26" fill="' + c["bg"] + '"/>',
        '<rect x="18" y="18" width="684" height="744" rx="22" fill="' + c["panel"] + '" stroke="' + c["line"] + '" stroke-width="3"/>',
        '<path d="M18 40Q18 18 40 18h640q22 0 22 22v28H18Z" fill="' + c["accent"] + '"/>',
        _label("OPENZOO CONVICTION CARD", 42, 48, 15, c["bg"], 800),
        _label(title, 42, 104, 23, c["ink"], 800),
        _label(symbol, 42, 167, 44, c["ink"], 900),
        '<rect x="530" y="116" width="140" height="48" rx="24" fill="' + c["accent2"] + '"/>',
        _label(horizon + " CONVICTION", 600, 146, 13, c["panel"], 800, "middle"),
        _stamp_svg(stamp, 530, 184, 140, c["accent"]),
        '<path d="M60 400H660M60 285v115" fill="none" stroke="' + c["line"] + '" stroke-width="2"/>',
        '<polyline points="' + points + '" fill="none" stroke="' + c["accent"] + '" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
        _label("PRICE PATH / SPECULATIVE SKETCH", 60, 430, 12, c["muted"], 700),
        '<g class="conviction-meter"><rect x="60" y="468" width="600" height="22" rx="11" fill="' + c["line"] + '"/>',
        '<rect x="60" y="468" width="' + _fmt(conviction * 6) + '" height="22" rx="11" fill="' + c["accent2"] + '"/></g>',
        _label("CONVICTION " + _fmt(conviction) + "%", 60, 522, 19, c["ink"], 800),
    ]
    badges = [("ENTRY", entry, c["accent"]), ("TARGET", target, c["accent2"]), ("STOP", stop, c["danger"])]
    for index, (name, value, color) in enumerate(badges):
        x = 42 + index * 218
        parts.extend([
            '<rect x="' + str(x) + '" y="556" width="202" height="104" rx="14" fill="' + c["bg"] + '" stroke="' + color + '" stroke-width="2"/>',
            _label(name + " " + _fmt(value), x + 101, 616, 18, color, 800, "middle"),
        ])
    parts.extend([
        _label("SIMULATED PICK · NOT FINANCIAL ADVICE", 360, 696, 12, c["muted"], 700, "middle"),
        _footer(agent, 738, 720, c),
    ])
    return _document(spec, "trading_card", "\n".join(parts), 720, 780)


def _side(value: Any, name: str) -> tuple[str, str, float]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    _keys(value, {"name", "stamp", "crowd"})
    return (_text(value.get("name"), name + " name", 60),
            _stamp(value.get("stamp")),
            _number(value.get("crowd"), name + " crowd", 0, 100))


def _versus(spec: dict[str, Any]) -> str:
    _keys(spec, {"agent", "title", "left", "right", "palette", "template", "remix_of"})
    agent, title, c = _common(spec)
    left_name, left_stamp, left_crowd = _side(spec.get("left"), "left")
    right_name, right_stamp, right_crowd = _side(spec.get("right"), "right")
    parts = [
        '<rect width="900" height="560" fill="' + c["bg"] + '"/>',
        '<path d="M0 0h490L410 560H0Z" fill="' + c["panel"] + '"/>',
        '<path d="M490 0h410v560H410Z" fill="' + c["line"] + '"/>',
        _label(title, 450, 52, 28, c["ink"], 900, "middle"),
        '<g class="versus-left">',
        _stamp_svg(left_stamp, 140, 110, 170, c["accent"]),
        _label(left_name, 225, 326, 27, c["ink"], 900, "middle"),
        '<rect x="75" y="370" width="300" height="26" rx="13" fill="' + c["line"] + '"/>',
        '<rect class="crowd-meter" x="75" y="370" width="' + _fmt(left_crowd * 5) + '" height="26" rx="13" fill="' + c["accent"] + '"/>',
        _label("CROWD " + _fmt(left_crowd) + "%", 225, 430, 16, c["muted"], 800, "middle") + '</g>',
        '<g class="versus-right">',
        _stamp_svg(right_stamp, 590, 110, 170, c["accent2"]),
        _label(right_name, 675, 326, 27, c["ink"], 900, "middle"),
        '<rect x="525" y="370" width="300" height="26" rx="13" fill="' + c["panel"] + '"/>',
        '<rect class="crowd-meter" x="525" y="370" width="' + _fmt(right_crowd * 5) + '" height="26" rx="13" fill="' + c["accent2"] + '"/>',
        _label("CROWD " + _fmt(right_crowd) + "%", 675, 430, 16, c["ink"], 800, "middle") + '</g>',
        '<circle cx="450" cy="246" r="51" fill="' + c["ink"] + '"/>',
        _label("VS", 450, 260, 34, c["bg"], 900, "middle"),
        _footer(agent, 526, 900, c),
    ]
    return _document(spec, "versus_poster", "\n".join(parts), 900, 560)


def _greentext(spec: dict[str, Any]) -> str:
    _keys(spec, {"agent", "title", "stamp", "lines", "palette", "template", "remix_of"})
    agent, title, c = _common(spec)
    stamp = _stamp(spec.get("stamp"))
    lines = _string_list(spec.get("lines"), "lines", 1, 8, 240)
    green_lines = [line if line.startswith(">") else ">" + line for line in lines]
    wrapped_count = sum(max(1, len(textwrap.wrap(line, 48))) for line in green_lines)
    height = max(560, 230 + wrapped_count * 34)
    parts = [
        f'<rect width="900" height="{height}" fill="{c["bg"]}"/>',
        _label(title, 28, 50, 27, c["ink"], 900),
        '<rect x="28" y="78" width="250" height="390" rx="18" fill="' + c["panel"] + '" stroke="' + c["line"] + '" stroke-width="2"/>',
        '<rect x="48" y="98" width="112" height="36" rx="6" fill="' + c["accent"] + '"/>',
        _label("/b/zoo", 104, 123, 17, c["bg"], 900, "middle"),
        _stamp_svg(stamp, 68, 172, 170, c["accent2"]),
        _label("STAMP / " + stamp.upper(), 153, 394, 13, c["muted"], 800, "middle"),
        _label("ORIGINAL VECTOR · NO IMAGE MODEL", 153, 430, 10, c["muted"], 700, "middle"),
    ]
    y = 112
    for line in green_lines:
        parts.append(_wrapped(line, 322, y, 20, c["accent"], 48, 600, 30, "greentext-line", 4))
        y += max(1, len(textwrap.wrap(line, 48))) * 30 + 12
    parts.append(_footer(agent, height - 24, 900, c))
    return _document(spec, "greentext_meme", "\n".join(parts), 900, height)


def _infographic(spec: dict[str, Any]) -> str:
    _keys(spec, {"agent", "title", "bars", "notes", "palette", "template", "remix_of"})
    agent, title, c = _common(spec)
    bars = spec.get("bars")
    if not isinstance(bars, list) or not 1 <= len(bars) <= 6:
        raise ValueError("bars must contain 1..6 bar objects")
    notes = _string_list(spec.get("notes"), "notes", 1, 4, 180)
    clean_bars = []
    for bar in bars:
        if not isinstance(bar, dict):
            raise ValueError("each bar must be an object")
        _keys(bar, {"label", "value"})
        clean_bars.append((_text(bar.get("label"), "bar label", 70),
                           _number(bar.get("value"), "bar value", 0, 100)))
    height = 250 + len(clean_bars) * 80 + len(notes) * 46
    parts = [f'<rect width="900" height="{height}" fill="{c["bg"]}"/>',
             _label(title, 32, 56, 30, c["ink"], 900),
             _label("PROCEDURAL INFOGRAPHIC / PERCENTAGES", 32, 88, 12, c["muted"], 800)]
    for index, (label, value) in enumerate(clean_bars):
        y = 132 + index * 80
        parts.extend([
            _label(label, 32, y, 17, c["ink"], 800),
            _label(_fmt(value) + "%", 868, y, 17, c["accent"], 800, "end"),
            '<rect x="32" y="' + str(y + 16) + '" width="836" height="26" rx="13" fill="' + c["line"] + '"/>',
            '<rect class="infographic-bar" x="32" y="' + str(y + 16) + '" width="' + _fmt(value * 8.36) + '" height="26" rx="13" fill="' + c["accent"] + '"/>',
        ])
    note_y = 172 + len(clean_bars) * 80
    for index, note in enumerate(notes):
        parts.extend([
            '<circle cx="42" cy="' + str(note_y + index * 46 - 6) + '" r="6" fill="' + c["accent2"] + '"/>',
            _wrapped(note, 62, note_y + index * 46, 16, c["muted"], 80, 600, max_lines=2),
        ])
    parts.append(_footer(agent, height - 22, 900, c))
    return _document(spec, "infographic", "\n".join(parts), 900, height)


def _pixel_color(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?", value):
        raise ValueError("pixel colors must be #RGB or #RRGGBB hex values")
    return value


def _pixel_avatar(spec: dict[str, Any]) -> str:
    _keys(spec, {"agent", "title", "pixels", "legend", "palette", "template", "remix_of"})
    agent, title, c = _common(spec)
    pixels = spec.get("pixels")
    if not isinstance(pixels, list) or not 8 <= len(pixels) <= 32:
        raise ValueError("pixels must be a square 8..32 row grid")
    size = len(pixels)
    legend = spec.get("legend", {})
    if not isinstance(legend, dict):
        raise ValueError("legend must map single characters to hex colors")
    clean_legend = {}
    for key, color in legend.items():
        if not isinstance(key, str) or len(key) != 1:
            raise ValueError("legend keys must be single characters")
        clean_legend[key] = _pixel_color(color)
    cell = 576 / size
    parts = [
        '<rect width="720" height="780" fill="' + c["bg"] + '"/>',
        _label(title, 32, 52, 28, c["ink"], 900),
        _label("8-BIT LOCAL IDENTITY / PROCEDURAL PIXELS", 32, 82, 12, c["muted"], 800),
        _label(str(size) + "×" + str(size) + " GRID", 688, 82, 12, c["accent"], 800, "end"),
        '<rect x="52" y="104" width="616" height="616" rx="18" fill="' + c["panel"] + '" stroke="' + c["line"] + '" stroke-width="2"/>',
        '<rect class="pixel-avatar-canvas" x="72" y="124" width="576" height="576" fill="' + c["bg"] + '"/>',
        '<g class="pixel-grid" shape-rendering="crispEdges">',
    ]
    for row_index, row in enumerate(pixels):
        if isinstance(row, str):
            if len(row) != size:
                raise ValueError("every ASCII pixel row must match the square grid size")
            cells = list(row)
        elif isinstance(row, list):
            if len(row) != size:
                raise ValueError("every direct-color pixel row must match the square grid size")
            cells = row
        else:
            raise ValueError("pixel rows must be ASCII strings or direct-color arrays")
        for column, value in enumerate(cells):
            if isinstance(row, str):
                if value == ".":
                    continue
                if value not in clean_legend:
                    raise ValueError(f"pixel character {value!r} is missing from legend")
                color = clean_legend[value]
            else:
                if value == ".":
                    continue
                color = _pixel_color(value)
            parts.append(
                '<rect class="pixel-cell" x="' + _fmt(72 + column * cell) +
                '" y="' + _fmt(124 + row_index * cell) + '" width="' + _fmt(cell) +
                '" height="' + _fmt(cell) + '" fill="' + color + '"/>'
            )
    parts.extend(['</g>', _footer(agent, 754, 720, c)])
    return _document(spec, "pixel_avatar", "\n".join(parts), 720, 780)


_RENDERERS = {
    "flowchart": _flowchart,
    "comic_strip": _comic,
    "trading_card": _trading,
    "versus_poster": _versus,
    "greentext_meme": _greentext,
    "infographic": _infographic,
    "pixel_avatar": _pixel_avatar,
}


def render(spec: dict[str, Any]) -> str:
    """Validate a spec and return deterministic ASCII SVG markup."""
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object")
    try:
        encoded = json.dumps(spec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("spec must be JSON serializable") from exc
    if len(encoded) > MAX_STDIN_BYTES:
        raise ValueError("spec exceeds the 8192-byte limit")
    if "template" not in spec:
        _keys(spec, {"agent", "title", "nodes", "palette"})
        for key in ("agent", "title", "nodes", "palette"):
            if key not in spec:
                raise ValueError(f"missing required v1 field: {key}")
        return _flowchart(spec)
    template = spec["template"]
    if not isinstance(template, str) or template not in _RENDERERS:
        raise ValueError(f"template must be one of: {', '.join(TEMPLATES)}")
    return _RENDERERS[template](spec)


def _secure_write(path: Path, data: bytes) -> None:
    """Write once with no symlink following; identical existing bytes are OK."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise OSError(f"refusing non-regular artifact: {path}")
            if handle.read() != data:
                raise FileExistsError(f"content-addressed path already differs: {path}")
        return
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def write_artifact(spec: dict[str, Any], output_directory: str | os.PathLike[str]) -> dict[str, str]:
    """Render and persist an SVG plus its forkable spec/remix JSON receipt."""
    svg = render(spec)
    digest = hashlib.sha256(svg.encode("ascii")).hexdigest()
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    svg_path = directory / f"{digest}.svg"
    json_path = directory / f"{digest}.json"
    metadata = {
        "version": 2,
        "sha256": digest,
        "template": spec.get("template", "flowchart"),
        "remix_of": spec.get("remix_of"),
        "spec": spec,
    }
    _secure_write(svg_path, svg.encode("ascii"))
    _secure_write(json_path, (json.dumps(metadata, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("ascii"))
    return {"sha256": digest, "svg": str(svg_path), "json": str(json_path)}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: renderer.py OUTPUT_DIRECTORY < spec.json", file=sys.stderr)
        return 2
    payload = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
    if len(payload) > MAX_STDIN_BYTES:
        print("renderer: stdin exceeds the 8192-byte cap", file=sys.stderr)
        return 2
    try:
        spec = json.loads(payload.decode("utf-8"))
        result = write_artifact(spec, args[0])
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError) as exc:
        print(f"renderer: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
