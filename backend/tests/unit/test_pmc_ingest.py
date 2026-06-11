from unittest.mock import AsyncMock

import httpx
import pytest
from lxml import etree

from app.ingest import pipeline, pmc_client
from app.ingest.pmc_client import _extract_methods_text
from app.models import Paper, PaperSource, Section


@pytest.mark.asyncio
async def test_doi_ingest_prefers_structured_pmc_full_text(monkeypatch):
    async def fake_find(_doi):
        return "PMC123"

    async def fake_fetch(_pmc_id):
        return Paper(
            paper_id="pmc:PMC123",
            source=PaperSource.PMC,
            title="PMC paper",
            sections={
                "methods": Section(
                    name="methods",
                    text="Cells were washed twice.",
                )
            },
        )

    async def unexpected_openalex(_doi):
        raise AssertionError("OpenAlex should not run after a PMC full-text hit")

    monkeypatch.setattr(pipeline.pmc_client, "find_pmc_by_doi", fake_find)
    monkeypatch.setattr(pipeline.pmc_client, "fetch_pmc", fake_fetch)
    monkeypatch.setattr(pipeline.openalex_client, "fetch_openalex_by_doi", unexpected_openalex)

    paper = await pipeline._fetch_doi("10.1000/example")

    assert paper is not None
    assert paper.paper_id == "doi:10.1000/example"
    assert paper.source == PaperSource.PMC
    assert paper.methods_text() == "Cells were washed twice."


def test_pmc_methods_keep_paragraphs_and_reference_ids_but_skip_tables_and_figures():
    article = etree.fromstring(
        b"""
        <article>
          <body>
            <sec>
              <title>STAR Methods</title>
              <table-wrap>
                <table><tr><td><p>Antibody catalog table should be skipped.</p></td></tr></table>
              </table-wrap>
              <sec>
                <title>Method Details</title>
                <p>
                  Cells were dissociated as described previously
                  <xref ref-type="bibr" rid="bib12">12</xref>.
                </p>
                <fig><caption><p>Figure caption should be skipped.</p></caption></fig>
                <p>Samples were centrifuged at 300g for 5 minutes.</p>
              </sec>
            </sec>
          </body>
        </article>
        """
    )

    methods = _extract_methods_text(article)

    assert "STAR Methods" in methods
    assert "Method Details" in methods
    assert "described previously [bib12]." in methods
    assert "Samples were centrifuged" in methods
    assert "catalog table" not in methods
    assert "Figure caption" not in methods


@pytest.mark.asyncio
async def test_pmc_request_retries_rate_limit(monkeypatch):
    request = httpx.Request("GET", pmc_client.EFETCH)
    responses = [
        httpx.Response(429, request=request, headers={"Retry-After": "0"}),
        httpx.Response(200, request=request, content=b"<article/>"),
    ]
    client = AsyncMock()
    client.get = AsyncMock(side_effect=responses)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    monkeypatch.setattr(pmc_client.httpx, "AsyncClient", lambda **_kwargs: client)
    monkeypatch.setattr(pmc_client, "_wait_for_request_slot", AsyncMock())

    response = await pmc_client._get_with_retry(
        pmc_client.EFETCH,
        params={"db": "pmc", "id": "123"},
        timeout=1.0,
    )

    assert response.status_code == 200
    assert client.get.await_count == 2
