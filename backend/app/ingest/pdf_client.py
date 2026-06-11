"""Download a PDF directly or discover one from an open repository landing page."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = "MethodsReconstructor/0.1 (research prototype)"
# M-15: Keywords that indicate a main-article PDF link (vs. supplemental/ad).
_PDF_PREFERRED_KEYWORDS = {"pdf", "full", "article", "download", "fulltext"}


def is_pdf_identifier(identifier: str) -> bool:
    value = identifier.strip()
    if value.lower().startswith(("http://", "https://")):
        return True
    path = Path(value).expanduser()
    return path.suffix.lower() == ".pdf" and path.is_file()


async def fetch_pdf(identifier: str) -> tuple[bytes, str] | None:
    value = identifier.strip()
    if not value.lower().startswith(("http://", "https://")):
        if get_settings().app_env != "development":
            log.warning("pdf.local_path_rejected", path=value)
            return None
        path = Path(value).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".pdf":
            return None
        if path.stat().st_size > MAX_PDF_BYTES:
            return None
        data = path.read_bytes()
        return (data, path.as_uri()) if _valid_pdf(data) else None

    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            data, final_url, content_type = await _safe_get(client, value)
            if _valid_pdf(data):
                return data, final_url
            if "html" not in content_type.lower() and not _looks_like_html(data):
                return None
            candidate = _find_pdf_url(
                data.decode("utf-8", errors="replace"),
                final_url,
            )
            if not candidate:
                return None
            pdf_data, pdf_url, _ = await _safe_get(client, candidate)
            if _valid_pdf(pdf_data):
                return pdf_data, pdf_url
    except Exception as e:
        log.warning("pdf.fetch_failed", identifier=value, error=str(e))
    return None


async def _safe_get(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[bytes, str, str]:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        await _validate_public_url(current)
        async with client.stream("GET", current) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response did not include a location")
                current = urljoin(str(response.url), location)
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            limit = MAX_HTML_BYTES if "html" in content_type.lower() else MAX_PDF_BYTES
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > limit:
                    raise ValueError(f"Remote response exceeded {limit} bytes")
            return bytes(data), str(response.url), content_type
    raise ValueError(f"Too many redirects while fetching {url}")


# C-6: CIDR ranges that must NEVER be contacted, regardless of is_global().
# Covers AWS/GCP/Azure metadata endpoints, link-local, ULA IPv6, carrier-grade NAT.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / AWS IMDSv1
    ipaddress.ip_network("100.64.0.0/10"),    # carrier-grade NAT
    ipaddress.ip_network("fd00::/8"),          # IPv6 ULA
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA broader
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),        # private
    ipaddress.ip_network("172.16.0.0/12"),     # private
    ipaddress.ip_network("192.168.0.0/16"),    # private
]


async def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) URLs are supported")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not supported")

    def resolve() -> set[str]:
        return {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }

    addresses = await asyncio.to_thread(resolve)
    if not addresses:
        raise ValueError("URL host did not resolve")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        # C-6: Check explicit block-list first (catches metadata IPs is_global misses).
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                raise ValueError(f"URL resolves to a blocked address range: {address}")
        if not ip.is_global:
            raise ValueError(f"URL resolves to a non-public address: {address}")


def _find_pdf_url(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    # Prefer structured meta tags — most reliable.
    for name in ("citation_pdf_url", "eprints.document_url"):
        meta = soup.find("meta", attrs={"name": name})
        if meta and meta.get("content"):
            return urljoin(base_url, str(meta["content"]))
    # M-15: Score links — prefer those with article/pdf/full in text or class.
    best_url: str | None = None
    best_score = -1
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if not urlparse(href).path.lower().endswith(".pdf"):
            continue
        score = 0
        text = (link.get_text(" ", strip=True) + " " + " ".join(link.get("class") or [])).lower()
        if any(kw in text for kw in _PDF_PREFERRED_KEYWORDS):
            score += 2
        if "supplement" in text or "appendix" in text or "suppl" in text:
            score -= 3  # deprioritize supplemental files
        if score > best_score:
            best_score = score
            best_url = urljoin(base_url, href)
    return best_url


def _valid_pdf(data: bytes) -> bool:
    return bool(data) and len(data) <= MAX_PDF_BYTES and data.lstrip().startswith(b"%PDF")


def _looks_like_html(data: bytes) -> bool:
    prefix = data.lstrip()[:100].lower()
    return prefix.startswith((b"<!doctype html", b"<html"))
