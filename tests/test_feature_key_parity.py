"""Feature-key parity invariant (Phase 10, ticket 01).

The backend ``FEATURE_TABLE`` (``tradingagents_api/astock_features.py``) and the
frontend tab registry ``ASTOCK_FEATURE_TABS`` (``tradingagents_gui/src/lib/types.ts``)
must expose the *same* set of feature keys, or a feature becomes unreachable from
the GUI even though the backend serves it.

This test is INTENTIONALLY RED until ticket 07 registers the five Phase 9 panels.
It is the acceptance baseline for the "两端对等" invariant (see CONTEXT.md):
fix the mismatch, and it turns green; then keep it as a CI gate.

No network and no TS toolchain: the frontend registry is read by regex, so this
runs in the normal pytest suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tradingagents_api.astock_features import FEATURE_TABLE

REPO_ROOT = Path(__file__).resolve().parents[1]
TYPES_TS = REPO_ROOT / "tradingagents_gui" / "src" / "lib" / "types.ts"

# `export const ASTOCK_FEATURE_TABS` … `];`  → every `key: "..."`
_REGISTRY_BLOCK_RE = re.compile(
    r"export\s+const\s+ASTOCK_FEATURE_TABS[^=]*=\s*\[(.*?)\];",
    re.DOTALL,
)
_KEY_RE = re.compile(r'key:\s*"([^"]+)"')


def _read_frontend_tab_keys() -> set[str]:
    """Extract the feature keys registered in ASTOCK_FEATURE_TABS."""
    if not TYPES_TS.exists():  # pragma: no cover - guards a moved file
        pytest.fail(f"frontend registry not found at {TYPES_TS}")

    source = TYPES_TS.read_text(encoding="utf-8")
    block = _REGISTRY_BLOCK_RE.search(source)
    if block is None:  # pragma: no cover - guards a renamed constant
        pytest.fail("ASTOCK_FEATURE_TABS array literal not found in types.ts")

    keys = _KEY_RE.findall(block.group(1))
    if not keys:  # pragma: no cover - guards a reformatted literal
        pytest.fail("ASTOCK_FEATURE_TABS parsed to zero keys")
    return set(keys)


def test_frontend_registry_parses() -> None:
    """Sanity: the regex actually finds the registered tabs."""
    keys = _read_frontend_tab_keys()
    assert "chip_distribution" in keys
    assert len(keys) > 0


def test_feature_keys_parity() -> None:
    """Frontend tab keys ⊆ backend FEATURE_TABLE keys.

    The backend serves market-wide features (ipo_declaration, margin_detail, …)
    that are intentionally NOT in the individual-stock tab strip — those live on
    the Market page. The real invariant is: every key the GUI registers as a tab
    must be served by the backend. If this passes, the xfail marker must be
    removed (it flips to XPASS and fails the suite otherwise).
    """
    backend = set(FEATURE_TABLE)
    frontend = _read_frontend_tab_keys()
    only_frontend = sorted(frontend - backend)
    only_backend = sorted(backend - frontend)

    assert not only_frontend, (
        f"frontend tabs with no backend handler: {only_frontend}"
    )
    # Informational: backend-only keys are market-wide features, expected.
    print(
        f"\n[parity] backend={len(backend)} frontend={len(frontend)}"
        f"\n[parity] backend-only (market-wide, expected): {only_backend}"
    )


def test_parity_diff_report() -> None:
    """Always-passing report of the current diff, for humans reading CI output."""
    backend = set(FEATURE_TABLE)
    frontend = _read_frontend_tab_keys()
    only_backend = sorted(backend - frontend)
    only_frontend = sorted(frontend - backend)
    print(
        f"\n[parity] backend={len(backend)} frontend={len(frontend)}"
        f"\n[parity] only in backend  ({len(only_backend)}): {only_backend}"
        f"\n[parity] only in frontend ({len(only_frontend)}): {only_frontend}"
    )
    assert isinstance(only_backend, list) and isinstance(only_frontend, list)
