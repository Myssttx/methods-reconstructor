"""Deterministic classification rules shared by extraction and offline tests."""

import re

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

EQUIPMENT_HINTS = [
    "microscope",
    "spectrometer",
    "illumina",
    "cytometer",
    "centrifuge",
    "pcr machine",
]
ANALYSIS_HINTS = [
    "t-test",
    "anova",
    "regression",
    "p <",
    "p<",
    "p =",
    "statistical",
    "graphpad",
    "spss",
    "r version",
]
SOFTWARE_HINTS = ["python", "version", "r (", "matlab", "fiji", "imagej", "github.com"]
DATASET_HINTS = ["dataset", "geo accession", "sra", "zenodo", "doi.org/10."]
REAGENT_HINTS = ["buffer", "antibody", "dmem", "fbs", "pbs", "tris", "edta"]


def classify_specificity(sentence: str) -> tuple[str, list[str]]:
    cited = [
        match.group(1)
        for match in re.finditer(
            r"\[(ref_?\d+|bib\d+|b\d+|r\d+|\d+)\]",
            sentence,
            re.IGNORECASE,
        )
    ]
    lowered = sentence.casefold()
    for pattern in SHORTCUT_PATTERNS:
        if re.search(pattern, sentence, re.IGNORECASE):
            return "shortcut_citation", cited
    for pattern in STANDARD_PATTERNS:
        if re.search(pattern, sentence, re.IGNORECASE):
            return "standard_unspecified", cited
    if any(hint in lowered for hint in PARTIAL_HINTS):
        return "partially_described", cited
    return "fully_described", cited


def classify_type(sentence: str) -> str:
    lowered = sentence.casefold()
    if any(hint in lowered for hint in ANALYSIS_HINTS):
        return "analysis"
    if any(hint in lowered for hint in SOFTWARE_HINTS):
        return "software"
    if any(hint in lowered for hint in DATASET_HINTS):
        return "dataset"
    if any(
        hint in lowered
        for hint in ["fixed", "stained", "lysed", "harvested", "cultured", "transfected"]
    ):
        return "sample_prep"
    if any(
        hint in lowered
        for hint in ["incubated", "centrifuged", "washed", "added", "mixed"]
    ):
        return "procedure"
    if any(hint in lowered for hint in EQUIPMENT_HINTS):
        return "equipment"
    if any(hint in lowered for hint in REAGENT_HINTS) or re.search(
        r"\b\d+(?:\.\d+)?\s*(?:mm|um|nm|molar)\b",
        lowered,
    ):
        return "reagent"
    return "procedure"
