import os
import streamlit as st
from anthropic import Anthropic


def _client() -> Anthropic:
    api_key = (
        st.secrets.get("ANTHROPIC_API_KEY", None)
        if hasattr(st, "secrets")
        else None
    ) or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found. Add it to .streamlit/secrets.toml or your environment."
        )
    return Anthropic(api_key=api_key)


def build_context(
    name: str,
    current_age: int,
    current_savings: float,
    monthly_contribution: float,
    allocation: str,
    goals: list,
    allocations: dict = None,
) -> str:
    lines = [
        f"Client: {name}",
        f"Age: {current_age}",
        f"Current savings: ${current_savings:,.0f}",
        f"Monthly contribution: ${monthly_contribution:,.0f}/mo",
        f"Asset allocation: {allocation}",
        "",
        "Goals (Monte Carlo success probabilities, 5,000 simulated paths):",
    ]
    for g in goals:
        alloc_note = ""
        if allocations and g.name in allocations:
            share = monthly_contribution * allocations[g.name] / 100
            alloc_note = f", funded with {allocations[g.name]}% of contributions (${share:,.0f}/mo)"
        lines.append(
            f"  - {g.name}: need ${g.target_amount:,.0f} by {g.target_year} "
            f"→ {g.probability * 100:.0f}% probability{alloc_note}"
        )
    return "\n".join(lines)


def stream_action_plan(context: str):
    """Yield streamed text for the AI action plan bullets."""
    client = _client()
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=450,
        system=(
            "You are a concise, direct financial advisor. The user has just run a Monte Carlo "
            "simulation of their financial plan. Based on the profile below, write exactly 3–5 "
            "specific, actionable bullet points. Reference the client's actual numbers. Lead with "
            "the highest-risk goal, then improvements, then reinforcements. Format each bullet "
            "starting with '• '. No intro sentence, no header, no closing line — only the bullets."
        ),
        messages=[{"role": "user", "content": context}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_chat(context: str, messages: list):
    """Yield streamed text for a chat response."""
    client = _client()
    system = (
        "You are a financial advisor assistant embedded in a financial planning dashboard. "
        "The client's current financial profile:\n\n"
        + context
        + "\n\nAnswer questions using their specific numbers. Be concise — under 120 words "
        "unless the user asks for more detail. When suggesting changes, quantify the impact "
        "where possible (e.g. 'adding $200/mo would likely raise your retirement probability "
        "from 58% to ~67%'). Never give generic advice — always tie back to their numbers."
    )
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
