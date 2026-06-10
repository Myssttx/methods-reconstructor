"""Unified LLM client.

Provider priority (chosen by `settings.resolved_llm_provider`):
  1. gemini    — google-genai SDK against Gemini 2.5 Pro / Flash
  2. anthropic — Anthropic SDK against Claude (drop-in for offline-no-Google teams)
  3. offline   — deterministic mock that returns plausible structured JSON
                 based on input keywords; used for tests + zero-cred demos.

Every call returns plain text. Callers that expect JSON parse it themselves
and handle the offline shape (which is already structured JSON).
"""

import asyncio
import json
import re
import time
import uuid
from typing import Any

import httpx

from app.config import get_settings
from app.llm.budget import charge_llm_text
from app.logging import get_logger

log = get_logger(__name__)

# Transient HTTP status codes worth retrying on.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


async def _retry_sleep(attempt: int) -> None:
    """Exponential backoff: 1s, 2s, 4s."""
    await asyncio.sleep(2 ** attempt)


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
    for m in re.finditer(r"\[(ref_\d+|b\d+|\d+)\]", sentence):
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
        charge_llm_text(f"{system or ''}\n{prompt}")
        # The agent calls into the offline LLM with a small set of stable prompts.
        # We branch on substring markers in the prompt body.
        if "Methods section:" in prompt or "<PAPER_CONTENT" in prompt:
            response = self._fake_decompose(prompt)
        elif "ORIGINAL_CLAIM" in prompt and "CANDIDATE_PASSAGE" in prompt:
            response = self._fake_locator(prompt)
        elif "Source paper:" in prompt and "CLAIMS_JSON" in prompt:
            response = self._fake_assemble(prompt)
        else:
            response = json.dumps({"unhandled": True, "preview": prompt[:200]})
        charge_llm_text(response)
        return response

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
        # Pull <CANDIDATE_PASSAGE ...> block
        idx = prompt.find("<CANDIDATE_PASSAGE")
        if idx >= 0:
            start = prompt.find(">", idx) + 1
            end = prompt.find("</CANDIDATE_PASSAGE>")
            passage = prompt[start:end].strip() if end > start else ""
        else:
            passage = ""
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
        charge_llm_text(f"{system or ''}\n{prompt}")
        cfg: dict[str, Any] = {"temperature": temperature}
        if response_format == "json":
            cfg["response_mime_type"] = "application/json"
        if system:
            cfg["system_instruction"] = system

        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=cfg,
                )
                text = resp.text or ""
                charge_llm_text(text)
                return text
            except Exception as e:
                status = getattr(getattr(e, "status_code", None), "value", None) or getattr(e, "status_code", 0)
                if attempt < _MAX_RETRIES - 1 and (status in _RETRYABLE_STATUS or "503" in str(e) or "429" in str(e)):
                    log.warning("llm.gemini_retry", attempt=attempt + 1, error=str(e))
                    await _retry_sleep(attempt)
                    last_err = e
                else:
                    raise
        raise RuntimeError(f"GeminiLLM failed after {_MAX_RETRIES} attempts") from last_err


class VertexADCGeminiLLM(LLMClient):
    """Gemini over Vertex AI REST using local Application Default Credentials."""

    def __init__(
        self,
        *,
        credentials_path: str,
        project_id: str,
        location: str,
        pro_model: str,
        flash_model: str,
        request_timeout_seconds: float,
    ) -> None:
        self.credentials_path = credentials_path
        self.project_id = project_id
        self.location = location or "global"
        self.pro = pro_model
        self.flash = flash_model
        self.request_timeout_seconds = request_timeout_seconds
        self._access_token = ""
        self._expires_at = 0.0
        with open(credentials_path, encoding="utf-8") as f:
            self.credentials = json.load(f)
        if self.credentials.get("type") != "authorized_user":
            raise ValueError("Only user ADC credentials are supported by this lightweight client")
        self.quota_project_id = self.credentials.get("quota_project_id") or project_id
        self._token_lock = asyncio.Lock()

    async def _token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        # H-8 fix: serialize refresh so concurrent callers don't all hit OAuth.
        async with self._token_lock:
            # Re-check after acquiring lock in case another coroutine refreshed.
            if self._access_token and time.time() < self._expires_at - 60:
                return self._access_token
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self.credentials["client_id"],
                        "client_secret": self.credentials["client_secret"],
                        "refresh_token": self.credentials["refresh_token"],
                        "grant_type": "refresh_token",
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
            self._access_token = payload["access_token"]
            self._expires_at = time.time() + int(payload.get("expires_in", 3600))
            return self._access_token

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
        charge_llm_text(f"{system or ''}\n{prompt}")
        url = (
            "https://aiplatform.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/"
            f"publishers/google/models/{model_name}:generateContent"
        )
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if response_format == "json":
            body["generationConfig"]["responseMimeType"] = "application/json"
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                token = await self._token()
                timeout = httpx.Timeout(
                    self.request_timeout_seconds,
                    connect=30.0,
                    write=30.0,
                    pool=30.0,
                )
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                            "x-goog-user-project": self.quota_project_id,
                        },
                        json=body,
                    )
                if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                    log.warning("llm.vertex_retry", attempt=attempt + 1, status=resp.status_code)
                    await _retry_sleep(attempt)
                    last_err = RuntimeError(f"Vertex HTTP {resp.status_code}")
                    continue
                resp.raise_for_status()
                payload = resp.json()
                parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
                charge_llm_text(text)
                return text
            except httpx.TimeoutException as e:
                if attempt < _MAX_RETRIES - 1:
                    log.warning("llm.vertex_timeout_retry", attempt=attempt + 1)
                    await _retry_sleep(attempt)
                    last_err = e
                else:
                    raise RuntimeError(
                        f"Vertex AI request to {model_name} timed out after "
                        f"{self.request_timeout_seconds:g} seconds"
                    ) from e
        raise RuntimeError(f"VertexADCGeminiLLM failed after {_MAX_RETRIES} attempts") from last_err


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
        charge_llm_text(f"{system or ''}\n{prompt}")
        settings = get_settings()
        model_id = "claude-opus-4-5" if model == "pro" else "claude-haiku-4-5-20251001"
        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self.client.messages.create(
                    model=model_id,
                    max_tokens=settings.llm_max_tokens,
                    system=system or "",
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                parts = [b.text for b in resp.content if hasattr(b, "text")]
                text = "\n".join(parts)
                charge_llm_text(text)
                return text
            except Exception as e:
                status = getattr(e, "status_code", 0)
                if attempt < _MAX_RETRIES - 1 and (status in _RETRYABLE_STATUS or "529" in str(e) or "overloaded" in str(e).lower()):
                    log.warning("llm.anthropic_retry", attempt=attempt + 1, error=str(e))
                    await _retry_sleep(attempt)
                    last_err = e
                else:
                    raise
        raise RuntimeError(f"AnthropicLLM failed after {_MAX_RETRIES} attempts") from last_err


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
        if (
            provider == "gemini"
            and settings.adc_credentials_path
            and settings.resolved_gcp_project_id
        ):
            log.info(
                "llm.init",
                provider="vertex_adc",
                project=settings.resolved_gcp_project_id,
                location=settings.vertex_ai_location,
            )
            _client = VertexADCGeminiLLM(
                credentials_path=settings.adc_credentials_path,
                project_id=settings.resolved_gcp_project_id,
                location=settings.vertex_ai_location,
                pro_model=settings.gemini_model_pro,
                flash_model=settings.gemini_model_flash,
                request_timeout_seconds=settings.llm_request_timeout_seconds,
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


def active_llm_provider() -> str:
    client = get_llm()
    if isinstance(client, GeminiLLM):
        return "gemini"
    if isinstance(client, VertexADCGeminiLLM):
        return "vertex_adc"
    if isinstance(client, AnthropicLLM):
        return "anthropic"
    return "offline"


def new_uuid() -> str:
    return str(uuid.uuid4())
