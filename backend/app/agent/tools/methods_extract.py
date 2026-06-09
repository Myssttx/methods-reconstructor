"""Methods decomposition tool. Gemini 2.5 Pro (or offline mock)."""

import json
import re
import uuid

from app.agent.prompts import METHODS_DECOMPOSITION_SYSTEM, METHODS_DECOMPOSITION_USER
from app.agent.schemas import DecompositionOutput
from app.config import get_settings
from app.llm.gemini_client import get_llm
from app.logging import get_logger
from app.models import Claim, ClaimType, Paper, ResolutionStatus, Specificity

log = get_logger(__name__)


async def extract_claims(paper: Paper) -> list[Claim]:
    methods = paper.sections.get("methods")
    if methods is None or not methods.text.strip():
        log.info("methods_extract.empty", paper_id=paper.paper_id)
        return []

    refs_list = "\n".join(f"- {r.ref_id}: {r.raw_citation[:200]}" for r in paper.references)
    settings = get_settings()
    llm = get_llm()
    raw_claims = []
    for chunk in _method_chunks(methods.text, settings.app_max_methods_chunk_chars):
        user_prompt = METHODS_DECOMPOSITION_USER.format(
            paper_id=paper.paper_id,
            title=paper.title,
            references_list=refs_list or "(none)",
            methods_text_with_sentence_ids=chunk,
        )
        response = await llm.complete(
            prompt=user_prompt,
            system=METHODS_DECOMPOSITION_SYSTEM,
            model="flash",
            response_format="json",
            temperature=settings.llm_temperature,
        )
        try:
            output = DecompositionOutput.model_validate(json.loads(response))
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(f"Methods decomposition returned invalid structured output: {e}") from e
        raw_claims.extend(output.claims)

    source_sentences = _stamped_sentences(methods.text)
    claims: list[Claim] = []
    seen_ids: set[str] = set()
    for raw in raw_claims:
        try:
            source_text = source_sentences.get(raw.raw_sentence_id)
            if source_text is None or _normalize(raw.raw_text) not in _normalize(source_text):
                log.warning(
                    "methods_extract.provenance_mismatch",
                    sentence_id=raw.raw_sentence_id,
                    raw_text=raw.raw_text[:200],
                )
                continue
            claim_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{paper.paper_id}|{raw.raw_sentence_id}|{raw.type.value}|"
                    f"{_normalize(raw.raw_text)}",
                )
            )
            if claim_id in seen_ids:
                continue
            seen_ids.add(claim_id)
            claims.append(
                Claim(
                    claim_id=claim_id,
                    paper_id=paper.paper_id,
                    type=ClaimType(raw.type),
                    raw_text=raw.raw_text,
                    raw_sentence_id=raw.raw_sentence_id,
                    specificity=Specificity(raw.specificity),
                    cited_ref_ids=raw.cited_ref_ids,
                    resolution_status=(
                        ResolutionStatus.RESOLVED
                        if raw.specificity == Specificity.FULLY_DESCRIBED
                        else ResolutionStatus.UNRESOLVED
                    ),
                    resolved_text=(
                        raw.raw_text
                        if raw.specificity == Specificity.FULLY_DESCRIBED
                        else None
                    ),
                )
            )
        except ValueError as e:
            log.warning("methods_extract.bad_claim", error=str(e), raw=raw.model_dump())
            continue

    if not claims:
        raise RuntimeError("Methods text was found, but no methodological claims were extracted")

    log.info("methods_extract.done", paper_id=paper.paper_id, n_claims=len(claims))
    return claims


def _method_chunks(text: str, max_chars: int) -> list[str]:
    """Chunk stamped methods text without splitting sentence-id lines."""
    lines = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for line in lines:
        line_size = len(line) + 1
        if current and current_size + line_size > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_size = 0
        current.append(line)
        current_size += line_size
    if current:
        chunks.append("\n".join(current))
    return chunks or [text]


def _stamped_sentences(text: str) -> dict[int, str]:
    return {
        int(match.group(1)): match.group(2).strip()
        for match in re.finditer(
            r"^\[(\d+)\]\s*(.*?)(?=^\[\d+\]\s|\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
    }


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold()
