"""Contract tests for the unified feature payload (ticket 02)."""

import pytest

from tradingagents_api.feature_payload import (
    FeatureKind,
    Format,
    Unit,
    raw_payload,
    validate_payload,
)


def _table_payload() -> dict:
    return {
        "kind": "table",
        "columns": [
            {"key": "code", "label": "代码"},
            {"key": "amt", "label": "净额", "unit": "万元", "format": "signed"},
        ],
        "rows": [{"code": "600519", "amt": -1234.5}],
        "provenance": {"source": "eastmoney", "as_of": "2026-09-27"},
    }


def test_valid_table_payload_roundtrips():
    out = validate_payload(_table_payload())
    assert out["kind"] == FeatureKind.TABLE.value
    assert out["columns"][1]["unit"] == Unit.WAN_YUAN.value
    assert out["columns"][1]["format"] == Format.SIGNED.value
    assert out["rows"] == [{"code": "600519", "amt": -1234.5}]
    assert out["provenance"]["as_of"] == "2026-09-27"


def test_defaults_applied():
    out = validate_payload(
        {"columns": [{"key": "a", "label": "A"}], "rows": [{"a": 1}]}
    )
    assert out["kind"] == FeatureKind.TABLE.value
    assert out["columns"][0]["unit"] == Unit.TEXT.value
    assert out["provenance"] == {"source": "", "as_of": "", "ttl_hint": None}


def test_raw_payload_is_explicit():
    out = raw_payload("# 未结构化", source="em", as_of="2026-09-27")
    assert out["kind"] == FeatureKind.RAW.value
    assert out["raw_md"] == "# 未结构化"
    assert out["provenance"]["source"] == "em"


def test_rejects_undeclared_row_key():
    bad = _table_payload()
    bad["rows"] = [{"code": "600519", "typo": 1}]
    with pytest.raises(ValueError, match="not declared in columns"):
        validate_payload(bad)


def test_rejects_empty_column_key():
    with pytest.raises(ValueError):
        validate_payload({"columns": [{"key": "", "label": "x"}], "rows": []})


def test_rejects_unknown_unit():
    with pytest.raises(ValueError):
        validate_payload(
            {"columns": [{"key": "a", "label": "A", "unit": "dollars"}], "rows": []}
        )
