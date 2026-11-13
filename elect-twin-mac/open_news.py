"""Transparent local Open News heuristics; never fetches or invents sources."""
import re
from urllib.parse import urlparse

# Shared by the Open News engine and the legacy story-spectrum API.
MEDIA_LEAN_LEXICON = {
    "left": ["workers", "union", "equity", "regulation", "antitrust", "climate", "public funding", "inequality", "safety net"],
    "right": ["free market", "deregulation", "tax cuts", "border", "patriot", "liberty", "mandate", "bureaucracy", "woke"],
    "center": ["analysis", "report", "data", "study", "survey", "consensus", "forecast", "review", "bipartisan"],
}
MEDIA_LEAN_TABLE = [
    {"outlet": "The Daily Cardinal", "lean": "left"},
    {"outlet": "Worker’s Herald", "lean": "left"},
    {"outlet": "The Ledger", "lean": "center"},
    {"outlet": "Wire Report", "lean": "center"},
    {"outlet": "Liberty Tribune", "lean": "right"},
    {"outlet": "The Free Press Gazette", "lean": "right"},
]
BUCKETS = ("left", "center", "right")


def _percentages(scores):
    # Add-one smoothing avoids a false zero-coverage claim. Largest remainders
    # make the integer buckets sum to exactly 100 without hiding the heuristic.
    weights = {key: scores[key] + 1 for key in BUCKETS}
    total = sum(weights.values())
    exact = {key: weights[key] * 100 / total for key in BUCKETS}
    result = {key: int(exact[key]) for key in BUCKETS}
    for key in sorted(BUCKETS, key=lambda item: (-(exact[item] - result[item]), BUCKETS.index(item)))[:100 - sum(result.values())]:
        result[key] += 1
    return result


def _sentences(text):
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()][:3]


def analyze_news(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    raw = payload.get("url_or_headline")
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 500:
        raise ValueError("url_or_headline must be nonempty text within 500 characters")
    source_text = payload.get("source_text", "")
    if not isinstance(source_text, str) or len(source_text) > 100000:
        raise ValueError("source_text must be text within 100000 characters")
    source_kind = payload.get("source_kind", "unverified")
    if source_kind not in ("primary", "unverified"):
        raise ValueError("source_kind must be primary or unverified")
    raw = raw.strip()
    source_text = source_text.strip()
    lower = (raw + "\n" + source_text).lower()
    parsed = urlparse(raw)
    is_url = parsed.scheme in ("http", "https") and bool(parsed.netloc)
    source = next((row["outlet"] for row in MEDIA_LEAN_TABLE if row["outlet"].lower() in lower), None)
    if source is None:
        source = parsed.netloc if is_url else "Headline submission (no outlet match in the 6-outlet lean table)"
    headline = re.sub(r"^https?://\S+\s*", "", raw).strip() or raw
    scores = {key: sum(1 for keyword in keywords if keyword in lower) for key, keywords in MEDIA_LEAN_LEXICON.items()}
    coverage = _percentages(scores)
    lean = max(BUCKETS, key=lambda key: (scores[key], coverage[key]))
    if not any(scores.values()):
        lean = "center"
    coverage["blindspot_alert"] = None
    if coverage[lean] < 30:
        coverage["blindspot_alert"] = "Under-covered on the " + lean + ": this submission may reflect a narrow keyword frame."
    sentences = _sentences(source_text)
    primary = source_kind == "primary" and bool(sentences)
    facts = list(sentences)
    inferences = [
        "Local lexicon classification suggests a " + lean + " keyword frame; this is not an outlet-verification result.",
        "Coverage percentages describe this submission's keyword distribution, not live outlet coverage.",
    ]
    unverified = []
    if not source_text:
        unverified.append("No article body or primary-source text was supplied.")
    if is_url and not source_text:
        unverified.append("The submitted URL was not fetched; its contents and provenance are unverified.")
    if not primary:
        unverified.append("No supplied primary-source text supports a verified core claim.")
    verified_core = {
        "verified": primary,
        "text": sentences[0] if primary else "COULDNT_VERIFY — attach primary-source text before treating a core claim as verified.",
    }
    frame_specs = (
        ("left", "Left-leaning frame hypothesis", "who gains and who pays"),
        ("center", "Center wire frame hypothesis", "what is confirmed and what is merely claimed"),
        ("right", "Right-leaning frame hypothesis", "what it could mean for markets and mandates"),
    )
    frames = [{"bucket": key, "label": label, "headline": prompt + ": " + headline, "verified": False} for key, label, prompt in frame_specs]
    divergence = max(coverage[key] for key in BUCKETS) - min(coverage[key] for key in BUCKETS)
    script = {
        "anchor": ["Submitted headline: " + headline, verified_core["text"]],
        "skeptic": ["Which claims lack primary evidence?", "How would each framing hypothesis change the emphasis?"],
    }
    verdict_card = (
        "FACT — " + ("; ".join(facts) if facts else "No source-text facts supplied.") + "\n"
        "INFERENCE — " + inferences[0] + "\n"
        "COULDNT_VERIFY — " + ("; ".join(unverified) if unverified else "Claims beyond the supplied primary-source extract remain unverified.")
    )
    return {
        "headline": headline,
        "submitted_source": source,
        "source_text_available": bool(source_text),
        "coverage_split": coverage,
        "divergence_score": divergence,
        "verified_core": verified_core,
        "facts": facts,
        "inferences": inferences,
        "unverified": unverified,
        "frames": frames,
        "audio_brief": {"available": False, "reason": "No speech engine connected", "script": script},
        "verdict_card": verdict_card,
        "method": "local 3-bucket lexicon heuristic; URLs are not fetched; no live coverage or audio verification",
        "comparative_headlines": [frame["label"] + ": " + frame["headline"] for frame in frames],
        "de_spinned_receipt": verdict_card,
    }
