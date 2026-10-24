"""Strict output schemas for every agent. Anything that fails validation is rejected."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CueOut(BaseModel):
    score: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    top_drivers: list[str] = Field(max_length=5)
    reason: str = Field(max_length=400)


class NewsOut(BaseModel):
    score: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[int]


class Objection(BaseModel):
    text: str = Field(max_length=300)
    severity: Literal["LOW", "MED", "HIGH"]


class RedTeamOut(BaseModel):
    objections: list[Objection]
    recommend_veto: bool


class ProposalOut(BaseModel):
    action: Literal["BUY", "SELL", "WAIT"]
    size_pct: float = Field(ge=0, le=2)
    thesis: str = Field(max_length=400)
    evidence_ids: list[int] = []
