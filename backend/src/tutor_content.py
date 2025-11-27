from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, TypedDict
import json

# --------- JSON content types --------- #

class ConceptDict(TypedDict):
    id: str
    title: str
    summary: str
    sample_question: str


@dataclass
class TutorConcept:
    id: str
    title: str
    summary: str
    sample_question: str


@dataclass
class TutorState:
    """Per-session tutor state, stored in session.userdata."""
    mode: Literal["welcome", "learn", "quiz", "teach_back"] = "welcome"
    current_concept_id: Optional[str] = None
    # you can extend this later for mastery tracking, scores, etc.
    times_explained: Dict[str, int] = field(default_factory=dict)
    times_quizzed: Dict[str, int] = field(default_factory=dict)
    times_taught_back: Dict[str, int] = field(default_factory=dict)


# --------- Load JSON content once --------- #

_THIS_DIR = Path(__file__).resolve().parent
_CONTENT_PATH = _THIS_DIR.parent / "shared-data" / "day4_tutor_content.json"

CONCEPTS: List[TutorConcept] = []
CONCEPT_BY_ID: Dict[str, TutorConcept] = {}
CONTENT_FOR_PROMPT: str = ""

def _load_content() -> None:
    global CONCEPTS, CONCEPT_BY_ID, CONTENT_FOR_PROMPT

    with _CONTENT_PATH.open("r", encoding="utf-8") as f:
        raw: List[ConceptDict] = json.load(f)

    CONCEPTS = [
        TutorConcept(
            id=item["id"],
            title=item["title"],
            summary=item["summary"],
            sample_question=item["sample_question"],
        )
        for item in raw
    ]
    CONCEPT_BY_ID = {c.id: c for c in CONCEPTS}

    # Nice string for LLM instructions
    lines = []
    for c in CONCEPTS:
        lines.append(
            f"- id: {c.id}\n"
            f"  title: {c.title}\n"
            f"  summary: {c.summary}\n"
            f"  sample_question: {c.sample_question}"
        )
    CONTENT_FOR_PROMPT = "\n".join(lines)

_load_content()


def get_default_concept_id() -> str:
    # default to first concept if nothing chosen
    return CONCEPTS[0].id if CONCEPTS else "variables"
