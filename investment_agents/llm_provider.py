"""Unified LLM provider — Google Gemini or OpenAI.

Gemini is preferred when GEMINI_API_KEY is set (fits Google AI / Gemini subscribers).
Falls back to OpenAI when only OPENAI_API_KEY is configured.
"""

from __future__ import annotations

from .config import settings


def provider_name() -> str:
    if settings.gemini_api_key:
        return "gemini"
    if settings.openai_api_key:
        return "openai"
    return "none"


def model_name() -> str | None:
    if settings.gemini_api_key:
        return settings.gemini_model
    if settings.openai_api_key:
        return settings.openai_model
    return None


def chat_completion(
    system: str,
    messages: list[dict],
    *,
    temperature: float = 0.55,
    max_tokens: int = 700,
) -> str:
    """Multi-turn chat. ``messages`` items: {role: user|assistant, content: str}."""
    if settings.gemini_api_key:
        return _gemini_chat(system, messages, temperature, max_tokens)
    if settings.openai_api_key:
        return _openai_chat(system, messages, temperature, max_tokens)
    raise RuntimeError("No LLM API key configured")


def json_completion(system: str, user: str, *, temperature: float = 0.2) -> str:
    """Single user turn; response should be JSON text."""
    if settings.gemini_api_key:
        return _gemini_json(system, user, temperature)
    if settings.openai_api_key:
        return _openai_json(system, user, temperature)
    raise RuntimeError("No LLM API key configured")


def _openai_chat(system: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    oai_messages = [{"role": "system", "content": system}]
    for m in messages:
        role = m.get("role", "user")
        if role in ("user", "assistant"):
            oai_messages.append({"role": role, "content": m.get("content", "")})
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=oai_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def _openai_json(system: str, user: str, temperature: float) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return (resp.choices[0].message.content or "").strip()


def _gemini_chat(system: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model,
        system_instruction=system,
    )

    history: list[dict] = []
    for m in messages[:-1]:
        role = m.get("role", "user")
        text = m.get("content", "")
        if role == "user":
            history.append({"role": "user", "parts": [text]})
        elif role == "assistant":
            history.append({"role": "model", "parts": [text]})

    last = messages[-1]["content"] if messages else ""
    chat = model.start_chat(history=history)
    resp = chat.send_message(
        last,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        },
    )
    return (resp.text or "").strip()


def _gemini_json(system: str, user: str, temperature: float) -> str:
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.gemini_model,
        system_instruction=system,
    )
    resp = model.generate_content(
        user,
        generation_config={
            "temperature": temperature,
            "response_mime_type": "application/json",
        },
    )
    return (resp.text or "").strip()
