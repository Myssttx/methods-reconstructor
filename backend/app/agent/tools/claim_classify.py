"""Single-sentence claim classifier — used in tests + as a sanity check."""

import json

from app.agent.prompts import METHODS_DECOMPOSITION_SYSTEM
from app.llm.gemini_client import get_llm


async def classify_sentence(sentence: str) -> dict:
    """Return {type, specificity, cited_ref_ids} for a single sentence."""
    prompt = (
        f"Methods section:\n[0] {sentence}\n\n"
        "Return JSON with a single key 'claims' as specified above."
    )
    llm = get_llm()
    resp = await llm.complete(prompt=prompt, system=METHODS_DECOMPOSITION_SYSTEM, model="flash")
    try:
        data = json.loads(resp)
        claims = data.get("claims", [])
        return claims[0] if claims else {}
    except json.JSONDecodeError:
        return {}
