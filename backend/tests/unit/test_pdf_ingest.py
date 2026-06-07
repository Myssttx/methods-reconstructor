import socket

import pytest

from app.ingest import pdf_client
from app.ingest.grobid_client import paper_from_tei
from app.ingest.pdf_client import _find_pdf_url

TEI = """\
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title level="a">A test paper</title></titleStmt>
      <publicationStmt><date when="2020-01-20"/></publicationStmt>
      <sourceDesc>
        <biblStruct>
          <analytic>
            <author><persName><forename>Jane</forename><surname>Doe</surname></persName></author>
          </analytic>
          <monogr><title>Test Journal</title></monogr>
        </biblStruct>
      </sourceDesc>
    </fileDesc>
    <profileDesc><abstract><div><p>Test abstract.</p></div></abstract></profileDesc>
  </teiHeader>
  <text>
    <body>
      <div><head>Introduction</head><p>Not methods.</p></div>
      <div>
        <head>Materials and methods</head>
        <p>Samples were processed as described previously <ref type="bibr" target="#b0">1</ref>.</p>
      </div>
      <div><head>Cohort selection</head><p>Thirty samples were included.</p></div>
      <div><head>Image analysis</head><p>Images were segmented with Tool X.</p></div>
      <div>
        <head>Survival models</head>
        <p>Models were fitted with Cox regression.</p>
        <p>37. Expert, P., Evans, T. S. A bibliography entry. Journal 1, 1-2 (2011).</p>
      </div>
      <div><head>Results</head><p>This result must not become a method.</p></div>
      <div><head>References</head><p>Bibliography text must not become a method.</p></div>
    </body>
    <back>
      <div type="references">
        <listBibl>
          <biblStruct xml:id="b0">
            <analytic><title>Prior protocol</title></analytic>
            <monogr><imprint><date when="2018"/></imprint></monogr>
            <idno type="DOI">10.1000/test</idno>
          </biblStruct>
        </listBibl>
      </div>
    </back>
  </text>
</TEI>
"""


def test_parse_grobid_tei_methods_and_references():
    paper = paper_from_tei(TEI, paper_id="doi:10.1000/example")
    assert paper is not None
    assert paper.title == "A test paper"
    assert paper.year == 2020
    assert paper.authors[0].name == "Jane Doe"
    assert "Samples were processed" in paper.methods_text()
    assert "Thirty samples were included" in paper.methods_text()
    assert "Images were segmented" in paper.methods_text()
    assert "Models were fitted" in paper.methods_text()
    assert "A bibliography entry" not in paper.methods_text()
    assert "This result must not become a method" not in paper.methods_text()
    assert "Bibliography text must not become a method" not in paper.methods_text()
    assert "[b0]" in paper.methods_text()
    assert paper.references[0].ref_id == "b0"
    assert paper.references[0].doi == "10.1000/test"
    assert paper.full_text_available is True


def test_find_repository_pdf_from_citation_meta():
    html = '<meta name="citation_pdf_url" content="/files/paper.pdf">'
    assert _find_pdf_url(html, "https://repository.example/item/1") == (
        "https://repository.example/files/paper.pdf"
    )


@pytest.mark.asyncio
async def test_pdf_fetch_rejects_private_network_targets(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ],
    )
    with pytest.raises(ValueError, match="non-public"):
        await pdf_client._validate_public_url("http://example.test/paper.pdf")
