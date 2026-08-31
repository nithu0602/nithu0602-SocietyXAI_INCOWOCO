"""Cheap live ping: one short completion per configured lab key. Skip empty keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from societyxai.utils.envfile import load_env_file  # noqa: E402

load_env_file(ROOT / ".env", ROOT.parent / ".env", Path.cwd() / ".env")

PROMPT = "Reply with the single word pong."


def _mask(value: str) -> str:
    if len(value) <= 10:
        return f"{value[:4]}…"
    return f"{value[:7]}…{value[-4:]}"


def _ok(name: str, model: str, text: str) -> None:
    snippet = " ".join(text.split())[:80]
    print(f"OK   {name:12} {model}")
    print(f"     reply: {snippet or '(empty)'}")


def _fail(name: str, model: str, detail: str) -> None:
    print(f"FAIL {name:12} {model}")
    print(f"     {detail[:280]}")


def ping_openai_compat(name: str, env_name: str, base_url: str, model: str, extra_headers: dict | None = None) -> bool:
    import os

    key = (os.environ.get(env_name) or "").strip()
    if not key:
        print(f"SKIP {name:12} {env_name} empty")
        return False
    print(f"PING {name:12} key={_mask(key)}  model={model}")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 8,
        "temperature": 0,
    }
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=45.0,
        )
    except httpx.HTTPError as exc:
        _fail(name, model, f"network: {exc}")
        return False
    if response.status_code >= 400:
        _fail(name, model, f"HTTP {response.status_code}: {(response.text or '')[:240]}")
        return False
    try:
        text = response.json()["choices"][0]["message"].get("content") or ""
        if isinstance(text, list):
            text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in text)
    except (ValueError, KeyError, IndexError, TypeError):
        _fail(name, model, f"bad json: {(response.text or '')[:200]}")
        return False
    _ok(name, model, text)
    return True


def ping_gemini() -> bool:
    import os

    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    model = "gemini-3.6-flash"
    if not key:
        print("SKIP gemini       GEMINI_API_KEY empty")
        return False
    print(f"PING gemini       key={_mask(key)}  model={model}")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
        "generationConfig": {"maxOutputTokens": 8, "temperature": 0},
    }
    try:
        response = httpx.post(url, params={"key": key}, json=payload, timeout=45.0)
    except httpx.HTTPError as exc:
        _fail("gemini", model, f"network: {exc}")
        return False
    if response.status_code >= 400:
        _fail("gemini", model, f"HTTP {response.status_code}: {(response.text or '')[:240]}")
        return False
    try:
        parts = response.json()["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (ValueError, KeyError, IndexError, TypeError):
        _fail("gemini", model, f"bad json: {(response.text or '')[:200]}")
        return False
    _ok("gemini", model, text)
    return True


def main() -> int:
    import os

    print("Cheap API ping for the free/PAYG seminar mix (max 8 tokens each).\n")
    results: dict[str, bool] = {}
    results["asha"] = ping_openai_compat(
        "asha/groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b"
    )
    results["mei"] = ping_gemini()
    or_env = "OPENROUTER_API_KEY" if (os.environ.get("OPENROUTER_API_KEY") or "").strip() else "DASHSCOPE_API_KEY"
    or_headers = {"HTTP-Referer": "https://github.com/societyxai", "X-Title": "SocietyXAI ping"}
    if or_env == "DASHSCOPE_API_KEY":
        print("NOTE openrouter   using DASHSCOPE_API_KEY (sk-or-…).")
    results["rahul"] = ping_openai_compat(
        "rahul/or", or_env, "https://openrouter.ai/api/v1",
        "meta-llama/llama-3.3-70b-instruct", extra_headers=or_headers,
    )
    results["ilya"] = ping_openai_compat(
        "ilya/or", or_env, "https://openrouter.ai/api/v1",
        "deepseek/deepseek-chat", extra_headers=or_headers,
    )
    results["noor"] = ping_openai_compat(
        "noor/or", or_env, "https://openrouter.ai/api/v1",
        "qwen/qwen3.5-flash-02-23", extra_headers=or_headers,
    )

    print("\n" + json.dumps({k: ("ok" if v else "fail") for k, v in results.items()}))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
