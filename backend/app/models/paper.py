from enum import Enum

from pydantic import BaseModel, Field


class PaperSource(str, Enum):
    ARXIV = "arxiv"
    PMC = "pmc"
    OPENALEX = "openalex"
    CROSSREF = "crossref"
    UPLOAD = "upload"
    FIXTURE = "fixture"


class Author(BaseModel):
    name: str
    orcid: str | None = None
    affiliation: str | None = None


class Reference(BaseModel):
    ref_id: str
    raw_citation: str
    doi: str | None = None
    arxiv_id: str | None = None
    pmc_id: str | None = None
    title: str | None = None
    year: int | None = None
    resolved: bool = False


class Section(BaseModel):
    name: str
    text: str
    sentence_offsets: list[tuple[int, int]] = Field(default_factory=list)


class Paper(BaseModel):
    paper_id: str
    source: PaperSource
    title: str
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    sections: dict[str, Section] = Field(default_factory=dict)
    references: list[Reference] = Field(default_factory=list)
    open_access_url: str | None = None
    full_text_available: bool = False
    ingested_at: str = ""

    def methods_text(self) -> str:
        return self.sections.get("methods", Section(name="methods", text="")).text
