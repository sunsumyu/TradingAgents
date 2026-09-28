"""Unified feature payload contract (Phase 11, ticket 02).

Every structured A-share feature is served as a single, uniform envelope so the
GUI can render it with one generic table component instead of per-panel code.
The envelope has four members:

* ``kind``        -- ``"table"`` for structured data, ``"raw"`` for the explicit
                     markdown degradation path.
* ``columns``     -- ordered list of column definitions
                     (``key``, ``label``, optional ``unit`` and ``format``).
* ``rows``        -- list of records; every record key must be a declared key.
* ``provenance``  -- ``source``, ``as_of`` (ISO date), optional ``ttl_hint``
                     in seconds.

Design rules (see docs/specs/2026-09-27-eastmoney-aligned-platform-plan.md §4):

* ``kind="raw"`` is the EXPLICIT degradation path -- it carries un-migrated
  markdown and is counted as tech debt, never the silent default.
* Dates are ISO ``YYYY-MM-DD``. Numeric columns declare a unit from the closed
  enum below and a format hint; the renderer never guesses.
* ``rows`` must align with ``columns``: every row key is a declared column key.

This module is additive -- it does not change how existing features are served.
Parsers opt in as they migrate (ticket 06 onwards).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Unit(str, Enum):
    """Closed unit vocabulary for numeric columns."""

    YUAN = "元"
    WAN_YUAN = "万元"
    YI_YUAN = "亿元"
    PERCENT = "percent"  # values are 0-100, renderer appends '%'
    SHARE = "股"
    WAN_SHARE = "万股"
    YI_SHARE = "亿股"
    RATIO = "ratio"  # dimensionless multiple, e.g. PE / PB
    COUNT = "count"
    DATE = "date"  # ISO YYYY-MM-DD string
    TEXT = "text"  # non-numeric


class Format(str, Enum):
    """Renderer hint; the renderer must not infer formatting."""

    INT = "int"
    FLOAT2 = "float2"  # two decimals
    FLOAT4 = "float4"
    DATE = "date"
    TEXT = "text"
    SIGNED = "signed"  # prefix '+' on positive numbers


class FeatureKind(str, Enum):
    TABLE = "table"
    RAW = "raw"


class Column(BaseModel):
    """One column definition."""

    key: str
    label: str
    unit: Unit = Unit.TEXT
    format: Format = Format.TEXT

    @field_validator("key")
    @classmethod
    def _key_nonempty(cls, v: str) -> str:
        if not v:
            raise ValueError("column key must be non-empty")
        return v


class Provenance(BaseModel):
    """Where one payload came from."""

    source: str = ""
    as_of: str = ""  # ISO date of the data
    ttl_hint: int | None = None  # seconds; consumed by ticket 11


class FeaturePayload(BaseModel):
    """Uniform structured feature payload."""

    kind: FeatureKind = FeatureKind.TABLE
    columns: list[Column] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    raw_md: str = ""  # only populated when kind == RAW


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw dict against the contract; raise ValueError on violation.

    Row/column alignment is checked here (rather than only inside the model) so
    the error message names the offending row index and keys.
    """
    model = FeaturePayload.model_validate(payload)
    column_keys = {c.key for c in model.columns}
    for i, row in enumerate(model.rows):
        unknown = set(row) - column_keys
        if unknown:
            raise ValueError(
                f"row {i} has keys not declared in columns: {sorted(unknown)}"
            )
    return model.model_dump(mode="json")


def raw_payload(raw_md: str, *, source: str = "", as_of: str = "") -> dict[str, Any]:
    """Build an explicit RAW payload for a not-yet-structured feature."""
    return FeaturePayload(
        kind=FeatureKind.RAW,
        raw_md=raw_md,
        provenance=Provenance(source=source, as_of=as_of),
    ).model_dump(mode="json")
