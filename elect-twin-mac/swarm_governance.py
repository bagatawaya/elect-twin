"""Deterministic, local-only parallel fan-out advice.

This module analyzes structure; it never starts workers or approves writes.
"""
import math
import re

POLICIES = {"notify_accept", "auto_optimize"}
SEQUENTIAL_OR_WRITE = re.compile(
    r"\b(sequential|sequentially|edit|editing|write|writing|deploy|publish|delete|"
    r"shared state|same file|then\s+(?:edit|write|deploy|publish|delete))\b",
    re.IGNORECASE,
)
TARGET_PATTERN = re.compile(r"https?://[^\s,]+|\$[A-Z][A-Z0-9.-]{0,14}")
BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", re.MULTILINE)


def _bounded_number(payload, key, default):
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(key + " must be a finite nonnegative number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(key + " must be a finite nonnegative number")
    return float(value)


def evaluate_swarm(payload):
    """Return a deterministic recommendation without executing any work."""
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20000:
        raise ValueError("prompt must be nonempty text within 20000 characters")
    policy = payload.get("swarm_policy", "notify_accept")
    if policy not in POLICIES:
        raise ValueError("Unsupported swarm_policy")
    targets = payload.get("targets")
    if targets is None:
        targets = TARGET_PATTERN.findall(prompt) + BULLET_PATTERN.findall(prompt)
    if (
        not isinstance(targets, list)
        or len(targets) > 32
        or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in targets)
    ):
        raise ValueError("targets must contain at most 32 bounded strings")
    targets = list(dict.fromkeys(item.strip() for item in targets))
    shared = payload.get("shared_paths", [])
    if not isinstance(shared, list) or len(shared) > 100 or any(
        not isinstance(item, str) or len(item) > 1000 for item in shared
    ):
        raise ValueError("shared_paths must be a bounded string array")
    if not isinstance(payload.get("shared_state", False), bool):
        raise ValueError("shared_state must be a boolean")
    if not isinstance(payload.get("external_write", False), bool):
        raise ValueError("external_write must be a boolean")

    collisions = ["shared_path:" + item for item in shared]
    if payload.get("shared_state") is True:
        collisions.append("shared_state")
    if SEQUENTIAL_OR_WRITE.search(prompt):
        collisions.append("sequential_or_write_intent")

    count = min(8, max(1, len(targets)))
    independent = count > 1 and not collisions
    tier = payload.get("tier", "free")
    if tier not in {"free", "local", "paid"}:
        raise ValueError("tier must be free, local, or paid")
    budget = _bounded_number(payload, "budget_cap_usd", 0.0)
    each = _bounded_number(payload, "cost_per_worker_usd", 0.0)
    if tier == "paid" and "cost_per_worker_usd" not in payload:
        raise ValueError("Paid tiers require an explicit worst-case cost_per_worker_usd")
    cost = round(count * each, 2) if tier == "paid" else 0.0

    reasons = []
    if not independent:
        reasons.append("no_independent_fan_out")
    if independent and cost > budget:
        reasons.append("budget_exceeded")
    recommend = independent and not reasons
    auto_activate = recommend and policy == "auto_optimize"
    return {
        "recommend": recommend,
        "auto_activate": auto_activate,
        "requires_acceptance": recommend and policy == "notify_accept",
        "worker_count": count if independent else 1,
        "estimated_speedup": round(1 + (count - 1) * 0.72, 2) if independent else 1.0,
        "worst_case_cost_usd": cost,
        "collisions": collisions,
        "reasons": reasons,
        "external_write_requires_approval": payload.get("external_write") is True,
        "policy": policy,
        "execution_started": False,
    }
