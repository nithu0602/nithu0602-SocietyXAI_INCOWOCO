from __future__ import annotations

SUPPORT = {
    "support",
    "approve",
    "yes",
    "pass",
    "terminate",
    "delay",
    "long",
    "true",
}
REJECT = {
    "reject",
    "no",
    "oppose",
    "fail",
    "abort",
    "keep",
    "short",
    "false",
}


def normalize_position(value: str | None) -> str:
    """Map yes/no/approve/reject-style labels onto support|reject|neutral."""
    if value is None:
        return "neutral"
    text = str(value).strip().lower()
    if text in SUPPORT:
        return "support"
    if text in REJECT:
        return "reject"
    if any(text.startswith(token) for token in ("yes", "approve", "support")):
        return "support"
    if any(text.startswith(token) for token in ("no", "reject", "oppose")):
        return "reject"
    if text in {"undecided", "unknown", "tie", "neutral", "abstain"}:
        return "neutral"
    return text
