import json
import logging
import re
from typing import Any, Optional

from openai import OpenAI

from app.services.settings_service import get_effective_config

logger = logging.getLogger("fnol.llm")


def _client() -> OpenAI:
    cfg = get_effective_config()
    if not cfg.get("llm_api_key"):
        raise RuntimeError(
            "No LLM API key configured. Enter one on the Settings page "
            "(Google/Gemini API key or any OpenAI-compatible key), or set "
            "LLM_API_KEY in the backend .env as a fallback."
        )
    return OpenAI(base_url=cfg["llm_base_url"], api_key=cfg["llm_api_key"])


def call_llm(system_prompt: str, user_prompt: str, expect_json: bool = True, max_retries: int = 2) -> Any:
    cfg = get_effective_config()
    client = _client()
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 2):
        try:
            resp = client.chat.completions.create(
                model=cfg["llm_model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            return json.loads(raw) if expect_json else raw
        except Exception as exc:
            last_exc = exc
            logger.warning("call_llm attempt %d/%d failed: %r", attempt, max_retries + 1, exc)
    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts") from last_exc


def test_llm_connection() -> dict:
    """Used by the Settings page's 'Test connection' button."""
    try:
        result = call_llm(
            "You are a connectivity test. Reply with ONLY this JSON: {\"ok\": true}",
            "ping",
            expect_json=True,
            max_retries=0,
        )
        return {"ok": bool(result.get("ok")), "detail": "LLM responded successfully."}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
