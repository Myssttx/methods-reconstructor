"""Methods decomposition with bounded Gemini Flash and deterministic fallback."""

import asyncio
import hashlib
import json
import re
import uuid

from app.agent.method_rules import classify_specificity, classify_type
from app.agent.prompts import METHODS_DECOMPOSITION_SYSTEM, METHODS_DECOMPOSITION_USER
from app.agent.schemas import DecompositionOutput, ExtractedClaim
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
    extraction_version = settings.methods_extraction_version
    source_methods_hash = hashlib.sha256(methods.text.encode()).hexdigest()
    source_sentences = _stamped_sentences(methods.text)
    if not source_sentences:
        raise RuntimeError("Methods text did not contain source sentence identifiers")

    use_rules = settings.app_methods_extraction_mode == "rules" or (
        settings.app_methods_extraction_mode == "hybrid"
        and len(source_sentences) >= settings.app_large_methods_sentence_threshold
    )
    if use_rules:
        mode = (
            "rules"
            if settings.app_methods_extraction_mode == "rules"
            else "rules_large_paper"
        )
        return _rule_claims(
            paper,
            source_sentences,
            extraction_version=extraction_version,
            source_methods_hash=source_methods_hash,
            extraction_mode=mode,
        )

    llm = get_llm()
    chunks = _method_chunks(methods.text, settings.app_max_methods_chunk_chars)
    semaphore = asyncio.Semaphore(settings.app_max_concurrent_llm_chunks)

    async def request_chunk(chunk: str):
        user_prompt = METHODS_DECOMPOSITION_USER.format(
            paper_id=paper.paper_id,
            title=paper.title,
            references_list=refs_list or "(none)",
            methods_text_with_sentence_ids=chunk,
        )
        async with semaphore:
            async with asyncio.timeout(settings.app_llm_chunk_timeout_seconds):
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
        return output.claims

    async def decompose_chunk(index: int, chunk: str):
        try:
            claims = await request_chunk(chunk)
            mode = "llm"
        except Exception as error:
            log.warning(
                "methods_extract.chunk_rules_fallback",
                paper_id=paper.paper_id,
                chunk_index=index,
                error=str(error) or type(error).__name__,
            )
            claims = _rule_extracted_claims(_stamped_sentences(chunk))
            mode = "rules_llm_fallback"
        return index, [(claim, mode) for claim in claims]

    try:
        async with asyncio.timeout(settings.app_extraction_wall_budget_seconds):
            chunk_outputs = await asyncio.gather(
                *(decompose_chunk(index, chunk) for index, chunk in enumerate(chunks))
            )
    except Exception as error:
        log.warning(
            "methods_extract.rules_fallback",
            paper_id=paper.paper_id,
            error=str(error) or type(error).__name__,
            n_chunks=len(chunks),
        )
        return _rule_claims(
            paper,
            source_sentences,
            extraction_version=extraction_version,
            source_methods_hash=source_methods_hash,
            extraction_mode="rules_llm_fallback",
        )
    raw_claims = [
        claim
        for _, claims in sorted(chunk_outputs)
        for claim in claims
    ]

    claims: list[Claim] = []
    seen_ids: set[str] = set()
    for raw, extraction_mode in raw_claims:
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
                    extraction_version=extraction_version,
                    extraction_mode=extraction_mode,
                    source_methods_hash=source_methods_hash,
                )
            )
        except ValueError as e:
            log.warning("methods_extract.bad_claim", error=str(e), raw=raw.model_dump())
            continue

    if not claims:
        raise RuntimeError("Methods text was found, but no methodological claims were extracted")

    log.info(
        "methods_extract.done",
        paper_id=paper.paper_id,
        n_claims=len(claims),
        n_chunks=len(chunks),
        extraction_mode=",".join(
            sorted({claim.extraction_mode for claim in claims})
        ),
    )
    return claims


def _rule_claims(
    paper: Paper,
    source_sentences: dict[int, str],
    *,
    extraction_version: str,
    source_methods_hash: str,
    extraction_mode: str,
) -> list[Claim]:
    claims: list[Claim] = []
    for raw in _rule_extracted_claims(source_sentences):
        normalized = _normalize(raw.raw_text)
        specificity = Specificity(raw.specificity)
        claim_type = ClaimType(raw.type)
        claim_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{paper.paper_id}|{raw.raw_sentence_id}|{claim_type.value}|{normalized}",
            )
        )
        fully_described = specificity == Specificity.FULLY_DESCRIBED
        claims.append(
            Claim(
                claim_id=claim_id,
                paper_id=paper.paper_id,
                type=claim_type,
                raw_text=raw.raw_text,
                raw_sentence_id=raw.raw_sentence_id,
                specificity=specificity,
                cited_ref_ids=raw.cited_ref_ids,
                resolution_status=(
                    ResolutionStatus.RESOLVED
                    if fully_described
                    else ResolutionStatus.UNRESOLVED
                ),
                resolved_text=raw.raw_text if fully_described else None,
                extraction_version=extraction_version,
                extraction_mode=extraction_mode,
                source_methods_hash=source_methods_hash,
            )
        )

    if not claims:
        raise RuntimeError("Methods text was found, but no methodological claims were extracted")
    log.info(
        "methods_extract.done",
        paper_id=paper.paper_id,
        n_claims=len(claims),
        n_chunks=0,
        extraction_mode=extraction_mode,
    )
    return claims


def _rule_extracted_claims(
    source_sentences: dict[int, str],
) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    for sentence_id, text in source_sentences.items():
        if not _normalize(text) or len(re.findall(r"[A-Za-z]+", text)) < 3:
            continue
        specificity, cited_ref_ids = classify_specificity(text)
        claims.append(
            ExtractedClaim(
                type=ClaimType(classify_type(text)),
                specificity=Specificity(specificity),
                cited_ref_ids=cited_ref_ids,
                raw_text=text,
                raw_sentence_id=sentence_id,
            )
        )
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
