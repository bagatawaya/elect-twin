"""Deterministic model-version selection within user-connected families."""
import json
import os
import re
import time
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

FAMILY_MODELS = {
    "kimi": {
        "fast_economical": ["kimi-k2.8", "Kimi 2.8"],
        "deep_reasoning": ["kimi-k3.1-pro", "Kimi 3.1 Pro"],
    },
    "gemini": {
        "fast_economical": ["gemini-2.5-flash", "Gemini 2.5 Flash"],
        "deep_reasoning": ["gemini-2.5-pro", "Gemini 2.5 Pro"],
    },
    "claude": {
        "fast_economical": ["claude-haiku", "claude-sonnet"],
        "deep_reasoning": ["claude-opus"],
    },
    "openrouter": {
        "fast_economical": ["openrouter/free"],
        "deep_reasoning": ["openrouter/frontier"],
    },
    "groq": {
        "fast_economical": ["groq/fast"],
        "deep_reasoning": ["groq/frontier"],
    },
    "ollama": {
        "fast_economical": ["ollama/fast"],
        "deep_reasoning": ["ollama/deep"],
    },
}
MODES = {"auto_optimize", "economy_lock", "frontier_max"}
TIERS = {"fast_economical", "deep_reasoning"}
DEEP = re.compile(
    r"\b(multi[- ]file|architecture|security|red.?team|math|sql|forensic|"
    r"debug|theorem|concurrency|cryptograph|formal proof)\b",
    re.IGNORECASE,
)


def _match(candidates, connected):
    lowered = {item.lower(): item for item in connected}
    for candidate in candidates:
        key = candidate.lower()
        if key in lowered:
            return lowered[key]
    for candidate in candidates:
        key = candidate.lower()
        for connected_key, original in lowered.items():
            if key in connected_key:
                return original
    return None


def route_model(payload):
    """Select a model ID only; never dispatch a provider request."""
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
        raise ValueError("prompt must be nonempty text within 20000 characters")
    family = payload.get("family", "kimi")
    mode = payload.get("mode", "auto_optimize")
    if family not in FAMILY_MODELS:
        raise ValueError("Unsupported model family")
    if mode not in MODES:
        raise ValueError("Unsupported routing mode")
    connected = payload.get("connected_models", [])
    if not isinstance(connected, list) or len(connected) > 100 or any(
        not isinstance(item, str) or not item.strip() or len(item) > 200 for item in connected
    ):
        raise ValueError("connected_models must be a bounded string array")
    skill_tier = payload.get("recommended_model_tier")
    if skill_tier is not None and skill_tier not in TIERS:
        raise ValueError("Unsupported recommended_model_tier")
    role = payload.get("room_role", "Builder")
    if role not in {"Builder", "Challenger"}:
        raise ValueError("room_role must be Builder or Challenger")
    file_count = payload.get("file_count", 0)
    if isinstance(file_count, bool) or not isinstance(file_count, int) or not 0 <= file_count <= 10000:
        raise ValueError("file_count must be an integer between 0 and 10000")
    context_tokens = payload.get("context_tokens", 0)
    if isinstance(context_tokens, bool) or not isinstance(context_tokens, int) or not 0 <= context_tokens <= 100000000:
        raise ValueError("context_tokens must be a nonnegative integer")

    deep = bool(
        DEEP.search(prompt)
        or skill_tier == "deep_reasoning"
        or role == "Challenger"
        or file_count > 3
        or context_tokens > 32000
    )
    tier = "deep_reasoning" if deep else "fast_economical"
    if mode == "economy_lock":
        tier = "fast_economical"
    elif mode == "frontier_max":
        tier = "deep_reasoning"
    selected = _match(FAMILY_MODELS[family][tier], connected)
    reasons = ["complexity:" + tier, "mode:" + mode]
    if skill_tier:
        reasons.append("matched_to_skill_tier")
    if role == "Challenger":
        reasons.append("challenger_counter_rubric")
    if not selected:
        reasons.append("no_connected_model_for_tier")
    return {
        "selected_model": selected,
        "tier": tier,
        "mode": mode,
        "family": family,
        "reasons": reasons,
        "alternatives": [item for item in connected if item != selected],
        "savings_label": (
            "Saves 50% configured credit tier"
            if family == "kimi" and tier == "fast_economical" and selected
            else None
        ),
        "available": selected is not None,
        "request_dispatched": False,
    }


class _NoPublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("Public model-index redirects are blocked")


_public_opener = build_opener(_NoPublicRedirect())


def _download_public_index(url, timeout, limit):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "OpenTwin-Public-Index/1"}, method="GET")
    with _public_opener.open(request, timeout=timeout) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise RuntimeError("Public model index exceeded 5 MB")
    return body


class OpenRouterIndex:
    """Opt-in public metadata only, with no credentials, redirects, or retries."""
    URL = "https://openrouter.ai/api/v1/models"
    LIMIT = 5000000
    TTL = 86400

    def __init__(self, path, transport=None):
        self.path = Path(path)
        self.transport = transport or _download_public_index

    def _load(self):
        try:
            if self.path.stat().st_size > self.LIMIT:
                return None
            cached = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(cached, dict) or not isinstance(cached.get("models"), list):
                return None
            fetched_at = cached.get("fetched_at")
            if isinstance(fetched_at, bool) or not isinstance(fetched_at, (int, float)):
                return None
            return cached
        except (OSError, ValueError, TypeError):
            return None

    @staticmethod
    def _models(raw):
        if not isinstance(raw, dict) or not isinstance(raw.get("data"), list) or len(raw["data"]) > 5000:
            raise ValueError("Invalid public model index")
        models = []
        for row in raw["data"]:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or len(row["id"]) > 200:
                continue
            pricing = row.get("pricing", {})
            if not isinstance(pricing, dict):
                pricing = {}
            clean = {"id": row["id"], "pricing": {}}
            for key in ("prompt", "completion"):
                value = pricing.get(key)
                if isinstance(value, (str, int, float)) and not isinstance(value, bool) and len(str(value)) <= 100:
                    clean["pricing"][key] = str(value)
            models.append(clean)
        return models[:2000]

    def get(self, consent=False, now=None):
        current = time.time() if now is None else now
        cached = self._load()
        if cached and 0 <= current - cached["fetched_at"] < self.TTL:
            return {"available": True, "cached": True, "fetched_at": cached["fetched_at"], "models": cached["models"], "source": self.URL}
        if consent is not True:
            return {"available": False, "cached": False, "models": [], "reason": "Explicit consent is required to refresh the public OpenRouter index; no network request made.", "source": self.URL}
        try:
            body = self.transport(self.URL, 15, self.LIMIT)
            if not isinstance(body, bytes) or len(body) > self.LIMIT:
                raise RuntimeError("Public model index exceeded 5 MB")
            document = {"fetched_at": current, "models": self._models(json.loads(body))}
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
            return {"available": True, "cached": False, "fetched_at": current, "models": document["models"], "source": self.URL}
        except Exception:
            return {"available": False, "cached": False, "models": [], "reason": "Public model index is offline or invalid; no automatic retry was made.", "source": self.URL}
