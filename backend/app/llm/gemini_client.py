"""Unified LLM client.

Provider priority (chosen by `settings.resolved_llm_provider`):
  1. gemini    — google-genai SDK against Gemini 2.5 Pro / Flash
  2. anthropic — Anthropic SDK against Claude (drop-in for offline-no-Google teams)
  3. offline   — deterministic mock that returns plausible structured JSON
                 based on input keywords; used for tests + zero-cred demos.

Every call returns plain text. Callers that expect JSON parse it themselves
and handle the offline shape (which is already structured JSON).
"""

import json
import re
import uuid
from typing import Any

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)


class LLMClient:
    async def complete(
        self,
        prompt: str,
        *,
        model: str = "pro",
        response_format: str = "text",
        system: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        raise NotImplementedError


# ---------- Offline (deterministic mock) ----------


SHORTCUT_PATTERNS = [
    r"as described (?:previously|in)",
    r"as (?:previously )?described",
    r"following the (?:protocol|method) of",
    r"following [A-Z][a-z]+ (?:et al\.?)?",
    r"see (?:supplementary|ref\.?|references?) for",
    r"performed as in",
    r"per the procedure of",
    r"\(ref_\d+\)",
]

STANDARD_PATTERNS = [
    r"standard (?:conditions|protocol|methods?)",
    r"as is conventional",
    r"according to manufacturer'?s instructions",
    r"per (?:the )?manufacturer",
]

PARTIAL_HINTS = ["briefly", "in brief", "approximately"]


REAGENT_HINTS = ["mM", "M ", "buffer", "antibody", "DMEM", "FBS", "PBS", "Tris", "EDTA"]
EQUIPMENT_HINTS = ["microscope", "spectrometer", "Illumina", "cytometer", "centrifuge", "PCR machine"]
ANALYSIS_HINTS = ["t-test", "ANOVA", "regression", "p <", "p<", "p =", "statistical", "GraphPad", "SPSS", "R version"]
SOFTWARE_HINTS = ["python", "version", "R (", "MATLAB", "Fiji", "ImageJ", "github.com"]
DATASET_HINTS = ["dataset", "GEO accession", "SRA", "Zenodo", "doi.org/10."]


def _classify_specificity(sentence: str) -> tuple[str, list[str]]:
    cited: list[str] = []
    # find inline ref tokens like [ref_3] or [12]
    for m in re.finditer(r"\[(ref_\d+|\d+)\]", sentence):
        cited.append(m.group(1))
    s = sentence.lower()
    for pat in SHORTCUT_PATTERNS:
        if re.search(pat, sentence, re.IGNORECASE):
            return "shortcut_citation", cited
    for pat in STANDARD_PATTERNS:
        if re.search(pat, sentence, re.IGNORECASE):
            return "standard_unspecified", cited
    if any(h in s for h in PARTIAL_HINTS):
        return "partially_described", cited
    return "fully_described", cited


def _classify_type(sentence: str) -> str:
    s = sentence.lower()
    if any(h.lower() in s for h in ANALYSIS_HINTS):
        return "analysis"
    if any(h.lower() in s for h in SOFTWARE_HINTS):
        return "software"
    if any(h.lower() in s for h in EQUIPMENT_HINTS):
        return "equipment"
    if any(h.lower() in s for h in DATASET_HINTS):
        return "dataset"
    if any(h in s for h in ["fixed", "stained", "lysed", "harvested", "cultured", "transfected"]):
        return "sample_prep"
    if any(h in s for h in ["incubated", "centrifuged", "washed", "added", "mixed"]):
        return "procedure"
    if any(h in s for h in ["mM", "buffer", "antibody"]):
        return "reagent"
    return "procedure"


class OfflineLLM(LLMClient):
    """Deterministic mock that produces structured JSON for the agent prompts."""

    async def complete(
        self,
        prompt: str,
        *,
        model: str = "pro",
        response_format: str = "text",
        system: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        # The agent calls into the offline LLM with a small set of stable prompts.
        # We branch on substring markers in the prompt body.
        if "Methods section:" in prompt:
            return self._fake_decompose(prompt)
        if "ORIGINAL_CLAIM" in prompt and "CANDIDATE_PASSAGE" in prompt:
            return self._fake_locator(prompt)
        if "Source paper:" in prompt and "Claims (JSON):" in prompt:
            return self._fake_assemble(prompt)
        return json.dumps({"unhandled": True, "preview": prompt[:200]})

    @staticmethod
    def _extract_methods_block(prompt: str) -> str:
        # Decomposition prompt suffix is "Methods section:\n{...}"
        idx = prompt.find("Methods section:")
        if idx < 0:
            return ""
        return prompt[idx + len("Methods section:") :].strip()

    def _fake_decompose(self, prompt: str) -> str:
        methods = self._extract_methods_block(prompt)
        # Split on sentence-id markers like [0], [12] at the start of a token.
        # Result alternates: [leading_text, sid, sentence_text, sid, ...]
        parts = re.split(r"\[(\d+)\]\s*", methods)
        sentences: list[tuple[str, str]] = []
        for i in range(1, len(parts) - 1, 2):
            sid = parts[i]
            text = parts[i + 1].strip()
            if text:
                sentences.append((sid, text))
        claims = []
        for sid, text in sentences:
            text = text.strip()
            if not text:
                continue
            specificity, cited = _classify_specificity(text)
            claims.append(
                {
                    "type": _classify_type(text),
                    "specificity": specificity,
                    "cited_ref_ids": cited,
                    "raw_text": text,
                    "raw_sentence_id": int(sid),
                }
            )
        # Fallback: if no [N] sentence markers were present, naively split.
        if not claims:
            for i, sent in enumerate(re.split(r"(?<=[.!?])\s+", methods)):
                sent = sent.strip()
                if not sent:
                    continue
                specificity, cited = _classify_specificity(sent)
                claims.append(
                    {
                        "type": _classify_type(sent),
                        "specificity": specificity,
                        "cited_ref_ids": cited,
                        "raw_text": sent,
                        "raw_sentence_id": i,
                    }
                )
        return json.dumps({"claims": claims})

    def _fake_locator(self, prompt: str) -> str:
        # Pull CANDIDATE_PASSAGE block
        idx = prompt.find("CANDIDATE_PASSAGE")
        passage = prompt[idx:].split("\n", 1)[1] if idx >= 0 else ""
        specificity, cited = _classify_specificity(passage)
        return json.dumps(
            {
                "fully_describes": specificity == "fully_described" and len(passage.strip()) > 60,
                "is_itself_shortcut": specificity == "shortcut_citation",
                "new_cited_refs": cited,
            }
        )

    def _fake_assemble(self, prompt: str) -> str:
        # Grab claims JSON
        idx = prompt.find("Claims (JSON):")
        if idx < 0:
            return json.dumps({"sections": {}, "gap_report": []})
        blob = prompt[idx + len("Claims (JSON):") :].strip()
        try:
            claims: list[dict[str, Any]] = json.loads(blob)
        except json.JSONDecodeError:
            claims = []
        sections: dict[str, list[dict[str, str]]] = {}
        gap_report: list[dict[str, str]] = []
        for c in claims:
            if c.get("resolution_status") == "terminal_gap":
                gap_report.append(
                    {
                        "claim_id": c["claim_id"],
                        "raw_text": c["raw_text"],
                        "reason": c.get("terminal_gap_reason") or "unknown",
                        "suggested_action": _suggest_action(c),
                    }
                )
            else:
                sec = c["type"]
                sections.setdefault(sec, []).append(
                    {
                        "claim_id": c["claim_id"],
                        "text": c.get("resolved_text") or c["raw_text"],
                    }
                )
        return json.dumps({"sections": sections, "gap_report": gap_report})


def _suggest_action(c: dict[str, Any]) -> str:
    reason = c.get("terminal_gap_reason")
    if reason == "depth_exceeded":
        return "Citation chain exceeds depth cap (5). Inspect chain trace manually."
    if reason == "paywall_or_dead":
        return "Cited paper not openly accessible. Try Unpaywall or contact the corresponding author."
    if reason == "no_match_in_cited":
        return "Cited paper does not describe this procedure. Search the broader corpus or contact the authors."
    if reason == "no_reference":
        return "No explicit citation in the source sentence. Contact the corresponding author."
    return "Contact the corresponding author for procedural detail."


# ---------- Real-provider stubs (lazy imports) ----------


class GeminiLLM(LLMClient):
    def __init__(self, api_key: str, pro_model: str, flash_model: str) -> None:
        from google import genai  # type: ignore[import-not-found]

        self.client = genai.Client(api_key=api_key)
        self.pro = pro_model
        self.flash = flash_model

    async def complete(
        self,
        prompt: str,
        *,
        model: str = "pro",
        response_format: str = "text",
        system: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        model_name = self.pro if model == "pro" else self.flash
        cfg: dict[str, Any] = {"temperature": temperature}
        if response_format == "json":
            cfg["response_mime_type"] = "application/json"
        if system:
            cfg["system_instruction"] = system

        resp = await self.client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=cfg,
        )
        return resp.text or ""


class AnthropicLLM(LLMClient):
    def __init__(self, api_key: str) -> None:
        from anthropic import AsyncAnthropic  # type: ignore[import-not-found]

        self.client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        prompt: str,
        *,
        model: str = "pro",
        response_format: str = "text",
        system: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        model_id = "claude-opus-4-5" if model == "pro" else "claude-haiku-4-5-20251001"
        resp = await self.client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=system or "",
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in resp.content if hasattr(b, "text")]
        return "\n".join(parts)


# ---------- Factory ----------


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    provider = settings.resolved_llm_provider
    try:
        if provider == "gemini" and settings.google_api_key:
            log.info("llm.init", provider="gemini")
            _client = GeminiLLM(
                api_key=settings.google_api_key,
                pro_model=settings.gemini_model_pro,
                flash_model=settings.gemini_model_flash,
            )
            return _client
        if provider == "anthropic" and settings.anthropic_api_key:
            log.info("llm.init", provider="anthropic")
            _client = AnthropicLLM(api_key=settings.anthropic_api_key)
            return _client
    except Exception as e:
        log.warning("llm.init_failed", provider=provider, error=str(e))

    log.info("llm.init", provider="offline")
    _client = OfflineLLM()
    return _client


def new_uuid() -> str:
    return str(uuid.uuid4())
