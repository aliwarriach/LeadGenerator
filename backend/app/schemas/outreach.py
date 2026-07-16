from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

OutreachToneLiteral = Literal["default", "direct", "value_first"]


class OutreachTone(StrEnum):
    DEFAULT = "default"
    DIRECT = "direct"
    VALUE_FIRST = "value_first"


class EmailGenerationResult(BaseModel):
    """Validated shape of the Groq model's JSON response for cold email
    generation — also the response body of POST /outreach/email/{lead_id}.

    One result per call, matching WhatsApp/Proposal — the caller now picks a
    tone explicitly (see OutreachTone) instead of getting an AI-decided
    bundle of variations to choose from after the fact.
    """

    subject: str
    email_body: str


class WhatsAppGenerationResult(BaseModel):
    """Validated shape of the Groq model's JSON response for WhatsApp
    message generation — also the response body of POST /outreach/whatsapp/{lead_id}."""

    message: str


class ProposalSection(BaseModel):
    heading: str
    content: str


class ProposalGenerationResult(BaseModel):
    """Validated shape of the Groq model's JSON response for proposal
    generation — also the response body of POST /outreach/proposal/{lead_id}."""

    title: str
    sections: list[ProposalSection] = Field(min_length=5)
