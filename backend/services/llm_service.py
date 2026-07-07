"""Pluggable LLM layer: hosted API (Anthropic) or local models via Ollama.

Everything above this module talks to two functions — summarize() and chat() —
so swapping backends is a config change, not a refactor. A "none" backend
degrades to extractive summaries so the app runs with no key and no GPU.

Context retrieval for the chatbot is pluggable too: register_context_provider()
lets future knowledge-repo sources add themselves without touching chat code.
"""
import textwrap
from typing import Callable

import requests

from backend import config
from backend.utils import cache

SYSTEM_PROMPT = (
    "You are VittaLens's research assistant for an internal investment team "
    "tracking Indian ETF indices (NIFTY 50, NIFTY Bank, NIFTY IT, CPSE, Bharat 22). "
    "Be concise, quantitative and neutral. Use the provided platform context when "
    "relevant, cite figures from it, and say clearly when you don't know. "
    "Nothing you say is investment advice."
)


# ── backends ───────────────────────────────────────────────────────────────────
class AnthropicBackend:
    name = "anthropic"

    def complete(self, system: str, messages: list[dict], max_tokens: int = 800) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        return resp.content[0].text


class OllamaBackend:
    """Local models via Ollama. deep=True routes to the larger analysis model
    (e.g. an 8B finance-tuned model), otherwise the fast 3B summariser."""
    name = "ollama"

    def __init__(self, deep: bool = False):
        self.model = config.OLLAMA_DEEP_MODEL if deep else config.OLLAMA_FAST_MODEL

    def complete(self, system: str, messages: list[dict], max_tokens: int = 800) -> str:
        resp = requests.post(
            f"{config.OLLAMA_HOST}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}] + messages,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class NoneBackend:
    """Keyless fallback: extractive, template-based text so every feature still
    renders. Marked so the UI can hint that a real LLM would do better."""
    name = "none"

    def complete(self, system: str, messages: list[dict], max_tokens: int = 800) -> str:
        return ""


def get_backend(deep: bool = False):
    if config.LLM_BACKEND == "anthropic" and config.ANTHROPIC_API_KEY:
        return AnthropicBackend()
    if config.LLM_BACKEND == "ollama":
        return OllamaBackend(deep=deep)
    return NoneBackend()


def llm_available() -> bool:
    return not isinstance(get_backend(), NoneBackend)


def _complete(prompt: str, system: str = SYSTEM_PROMPT, deep: bool = False,
              max_tokens: int = 800) -> str:
    backend = get_backend(deep=deep)
    if isinstance(backend, NoneBackend):
        return ""
    try:
        return backend.complete(system, [{"role": "user", "content": prompt}], max_tokens).strip()
    except Exception:
        return ""


# ── summarization ──────────────────────────────────────────────────────────────
def summarize_news_item(title: str, raw_summary: str) -> str:
    """2–3 line card summary for a news item; extractive fallback."""
    text = _complete(
        f"Summarise this financial news item in 2-3 plain sentences for an "
        f"investment team. No preamble.\n\nHeadline: {title}\n\nBody: {raw_summary}",
        deep=False, max_tokens=160,
    )
    return text or textwrap.shorten(raw_summary or title, width=280, placeholder="…")


def daily_digest(headlines: list[str]) -> str:
    """One-paragraph market overview from today's top headlines."""
    joined = "\n".join(f"- {h}" for h in headlines[:25])
    text = _complete(
        "Write ONE tight paragraph (4-6 sentences) synthesising today's most "
        "important market developments for an Indian investment team, from these "
        f"headlines. Plain prose, no list, no preamble.\n\n{joined}",
        deep=False, max_tokens=300,
    )
    return text or (
        "LLM summarisation is not configured (set LLM_BACKEND in .env). "
        "Today's top headlines: " + "; ".join(headlines[:6]) + "."
    )


def investment_brief(symbol: str, profile: dict, news_items: list[dict]) -> dict:
    """LLM investment brief for a company from fundamentals + scraped news."""
    def build() -> dict:
        news_text = "\n".join(
            f"- {n['title']} ({n.get('source', '')}): {n.get('summary', '')[:200]}"
            for n in news_items[:10]
        ) or "(no recent news found)"
        q = profile.get("quote", {})
        prompt = (
            f"Write a concise investment brief for {profile.get('name', symbol)} ({symbol}), "
            "in markdown with exactly these four short sections: "
            "**Key Developments**, **Sentiment**, **Risks**, **Outlook**.\n\n"
            f"Fundamentals: price ₹{q.get('price')}, day {q.get('day_change_pct')}%, "
            f"P/E {q.get('pe')}, P/B {q.get('pb')}, dividend yield {q.get('div_yield')}%, "
            f"ROE {q.get('roe')}%, sector {profile.get('sector')}.\n\n"
            f"Recent news:\n{news_text}"
        )
        text = _complete(prompt, deep=True, max_tokens=700)
        if not text:
            text = (
                f"**Key Developments**\n\nLLM summarisation is not configured. "
                f"Recent headlines for {symbol}:\n\n"
                + "\n".join(f"- {n['title']}" for n in news_items[:5])
                + "\n\n**Sentiment / Risks / Outlook**\n\nSet `LLM_BACKEND` in `.env` "
                "(anthropic or ollama) to enable AI-generated analysis."
            )
        return {"symbol": symbol, "brief_md": text, "llm": get_backend(True).name}

    try:
        return cache.get_or_fetch(f"brief:{symbol}", config.TTL_LLM, build)
    except Exception:
        return build()


# ── pluggable chat context ─────────────────────────────────────────────────────
_context_providers: list[Callable[[str], str]] = []


def register_context_provider(fn: Callable[[str], str]) -> None:
    """fn(user_message) -> context text ('' to contribute nothing).
    Future knowledge-repo / document sources plug in here."""
    _context_providers.append(fn)


def gather_context(user_message: str) -> str:
    parts = []
    for fn in _context_providers:
        try:
            text = fn(user_message)
            if text:
                parts.append(text)
        except Exception:
            continue
    return "\n\n".join(parts)


# ── chat sessions (in-memory, per browser session id) ─────────────────────────
_sessions: dict[str, list[dict]] = {}
MAX_TURNS = 30


def chat(session_id: str, user_message: str) -> dict:
    history = _sessions.setdefault(session_id, [])
    context = gather_context(user_message)
    system = SYSTEM_PROMPT + ("\n\n--- Platform context ---\n" + context if context else "")

    backend = get_backend(deep=True)
    if isinstance(backend, NoneBackend):
        reply = (
            "No LLM backend is configured. Set `LLM_BACKEND=anthropic` (with an "
            "API key) or `LLM_BACKEND=ollama` (with a local model pulled) in `.env` "
            "and restart. Meanwhile, here is the live platform context I would "
            "have used:\n\n" + (context or "(no context available)")
        )
    else:
        try:
            reply = backend.complete(system, history + [{"role": "user", "content": user_message}])
        except Exception as exc:
            reply = f"The LLM backend ({backend.name}) returned an error: {exc}"

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})
    del history[:-MAX_TURNS * 2]
    return {"reply": reply, "backend": backend.name, "turns": len(history) // 2}


def get_history(session_id: str) -> list[dict]:
    return _sessions.get(session_id, [])


def clear_history(session_id: str) -> None:
    _sessions.pop(session_id, None)
