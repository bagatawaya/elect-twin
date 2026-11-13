"""Versioned five-tab dashboard layout with strict, atomic local persistence."""
import copy
import json
import os
import re
from pathlib import Path

DASHBOARD_SPANS = {"1x1", "2x1", "2x2"}
MAX_WIDGETS_PER_TAB = 12
MAX_CUSTOM_TABS = 8
LENS_IDS = {
    "open-source-ai", "vibe-coding", "macro-markets", "geopolitics",
    "pro-sports", "crypto", "bio-health", "media-music",
}
WIDGET_TITLES = {
    "my_models_hub": "🧠 My Models, Version Router & Benchmark",
    "openskills_library": "🧩 OpenSkills v2 Optimizer",
    "morning_postcard": "While You Were Out",
    "project_decisions": "Pinned Decisions",
    "task_center_live_feed": "⏱️ Task Center Live Feed",
    "airlock_privacy_diff": "Airlock Privacy Diff",
    "open_news_engine": "📰 Open News",
    "multimodal_model_tracker": "Multimodal Model Tracker",
    "personal_blind_scorecard": "Personal Blind Scorecard",
    "builder_signal_radar": "Builder Signal Radar",
    "pro_sports_odds_board": "Pro Sports Odds Board",
    "macro_alpha_delta": "Macro Alpha Delta",
    "zoo_arena_pulse_cta": "OpenZoo Arena Pulse",
    "room_zero_lockbox": "Room Zero Lockbox",
    "imageboard_media_remix": "Imageboard Media Remix",
    "custom_task_widget": "Task Results",
    # v1 widget types remain valid so existing customizations migrate losslessly.
    "model_market_tracker": "Frontier Model Intelligence",
    "global_agent_telemetry": "The Live Zoo Pulse",
    "model_scorecard": "Blind Scrimmage Scorecard",
    "airlock_diff": "Outbound Sanitizer Diff",
    "zoo_odds_watch": "Arena Odds Watch",
    "fork_crew_spotlight": "Fork Crew Spotlight",
    "story_spectrum_mapper": "News Spectrum & Spin Mapper",
    "model_tracker_hub": "Model Tracker Hub",
}
WIDGET_TYPES = set(WIDGET_TITLES)
TAB_DEFINITIONS = (
    ("command", "🏠 My Command"),
    ("news", "📰 Open News"),
    ("ai-code", "🧠 My AI & Code"),
    ("markets", "📈 My Markets & Odds"),
    ("zoo-studio", "🔭 My Zoo & Studio"),
)
DEFAULT_WIDGETS = {
    "command": (
        ("my_models_hub", "2x1"), ("openskills_library", "1x1"),
        ("morning_postcard", "2x1"), ("project_decisions", "1x1"),
        ("task_center_live_feed", "1x1"), ("airlock_privacy_diff", "2x1"),
    ),
    "news": (("open_news_engine", "2x2"),),
    "ai-code": (
        ("my_models_hub", "2x2"), ("openskills_library", "2x1"),
        ("multimodal_model_tracker", "2x2"), ("personal_blind_scorecard", "1x1"),
        ("builder_signal_radar", "1x1"),
    ),
    "markets": (("pro_sports_odds_board", "2x1"), ("macro_alpha_delta", "2x1")),
    "zoo-studio": (
        ("zoo_arena_pulse_cta", "2x1"), ("room_zero_lockbox", "1x1"),
        ("imageboard_media_remix", "1x1"),
    ),
}


def _widget(widget_type, span, tab_id, order):
    return {
        "id": "dash-" + tab_id + "-" + widget_type,
        "type": widget_type,
        "title": WIDGET_TITLES[widget_type],
        "span": span,
        "config": {},
        "order": order,
    }


def default_layout():
    tabs = []
    for tab_id, title in TAB_DEFINITIONS:
        tabs.append({
            "id": tab_id,
            "title": title,
            "kind": "system",
            "widgets": [_widget(kind, span, tab_id, index) for index, (kind, span) in enumerate(DEFAULT_WIDGETS[tab_id])],
        })
    return {"schema_version": 2, "active_tab": "command", "lens": [], "tabs": tabs}


def _validate_widgets(widgets, allow_empty=True):
    if not isinstance(widgets, list) or (not allow_empty and not widgets):
        raise ValueError("Layout widgets must be a nonempty array" if not allow_empty else "Tab widgets must be an array")
    if len(widgets) > MAX_WIDGETS_PER_TAB:
        raise ValueError("Too many widgets in one tab")
    cleaned = []
    seen = set()
    for index, widget in enumerate(widgets):
        if not isinstance(widget, dict):
            raise ValueError("Each widget must be an object")
        if set(widget) - {"id", "type", "title", "span", "config", "order"}:
            raise ValueError("Unsupported widget field")
        widget_type = widget.get("type")
        if widget_type not in WIDGET_TYPES:
            raise ValueError("Unsupported widget type")
        widget_id = widget.get("id")
        if not isinstance(widget_id, str) or not widget_id.strip() or len(widget_id) > 80:
            raise ValueError("Widget id must be nonempty text within 80 characters")
        if widget_id in seen:
            raise ValueError("Duplicate widget id in tab")
        seen.add(widget_id)
        title = widget.get("title", WIDGET_TITLES[widget_type])
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            raise ValueError("Widget title must be nonempty text within 120 characters")
        span = widget.get("span", "1x1")
        if isinstance(span, bool):
            raise ValueError("Widget span must be 1x1, 2x1, or 2x2")
        if isinstance(span, int):
            span = {1: "1x1", 2: "2x1"}.get(span)
        if span not in DASHBOARD_SPANS:
            raise ValueError("Widget span must be 1x1, 2x1, or 2x2")
        config = widget.get("config", {})
        if not isinstance(config, dict) or len(json.dumps(config, ensure_ascii=False)) > 4000:
            raise ValueError("Widget config must be a bounded object")
        cleaned.append({
            "id": widget_id, "type": widget_type, "title": title.strip(),
            "span": span, "config": copy.deepcopy(config), "order": index,
        })
    return cleaned


def migrate_layout(raw):
    if isinstance(raw, dict) and raw.get("schema_version") == 2:
        return validate_layout(raw)
    if isinstance(raw, dict) and set(raw) == {"widgets"}:
        raw = raw["widgets"]
    if not isinstance(raw, list):
        raise ValueError("Layout must be a v1 widget array or v2 document")
    widgets = _validate_widgets(raw, allow_empty=False)
    document = default_layout()
    document["tabs"][0]["widgets"] = widgets
    return document


def validate_layout(raw):
    if not isinstance(raw, dict) or raw.get("schema_version") != 2:
        raise ValueError("Layout schema_version must be 2")
    if set(raw) - {"schema_version", "active_tab", "lens", "tabs"}:
        raise ValueError("Unsupported layout field")
    tabs = raw.get("tabs")
    if not isinstance(tabs, list):
        raise ValueError("Layout tabs must be an array")
    lens = raw.get("lens", [])
    if not isinstance(lens, list) or len(lens) > len(LENS_IDS) or any(item not in LENS_IDS for item in lens):
        raise ValueError("Unsupported OS lens")
    if len(set(lens)) != len(lens):
        raise ValueError("Duplicate OS lens")
    fixed = {item[0] for item in TAB_DEFINITIONS}
    cleaned_tabs = []
    seen_tabs = set()
    seen_widgets = set()
    custom_count = 0
    for tab in tabs:
        if not isinstance(tab, dict) or set(tab) - {"id", "title", "kind", "widgets"}:
            raise ValueError("Unsupported tab field")
        tab_id = tab.get("id")
        kind = tab.get("kind")
        title = tab.get("title")
        if not isinstance(tab_id, str) or tab_id in seen_tabs:
            raise ValueError("Tab ids must be unique strings")
        if kind == "system":
            if tab_id not in fixed or title != dict(TAB_DEFINITIONS)[tab_id]:
                raise ValueError("Invalid system tab")
        elif kind == "custom":
            custom_count += 1
            if not re.fullmatch(r"custom-[A-Za-z0-9-]{1,50}", tab_id):
                raise ValueError("Invalid custom tab id")
            if not isinstance(title, str) or not title.strip() or len(title) > 60:
                raise ValueError("Custom tab title must be within 60 characters")
        else:
            raise ValueError("Tab kind must be system or custom")
        seen_tabs.add(tab_id)
        widgets = _validate_widgets(tab.get("widgets"))
        if seen_widgets.intersection(widget["id"] for widget in widgets):
            raise ValueError("Widget ids must be unique across tabs")
        seen_widgets.update(widget["id"] for widget in widgets)
        cleaned_tabs.append({"id": tab_id, "title": title.strip(), "kind": kind, "widgets": widgets})
    if seen_tabs.intersection(fixed) != fixed:
        raise ValueError("All five system tabs are required")
    if custom_count > MAX_CUSTOM_TABS:
        raise ValueError("Too many custom tabs")
    active = raw.get("active_tab", "command")
    if active not in seen_tabs:
        raise ValueError("active_tab does not exist")
    return {"schema_version": 2, "active_tab": active, "lens": list(lens), "tabs": cleaned_tabs}


class DashboardStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return default_layout()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return migrate_layout(raw)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return default_layout()

    def save(self, raw):
        cleaned = migrate_layout(raw) if not isinstance(raw, dict) or raw.get("schema_version") != 2 else validate_layout(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        os.chmod(self.path, 0o600)
        return cleaned
