# src/e2e/test_augment_query.py

import re
import pytest

from backend.search import augment_query
import backend.search as S  # to monkeypatch normalize_only


class FakeIndex:
    """
    Minimal index double for augment_query:
      - _term_lex: sorted list of terms (corpus vocabulary)
      - _postings: dict term -> list (length used as term frequency)
    """
    def __init__(self, tf: dict[str, int]):
        self._term_lex = sorted(tf.keys())
        self._postings = {t: [0] * int(tf[t]) for t in tf}


@pytest.fixture(autouse=True)
def patch_normalize_only(monkeypatch):
    """
    Make normalization predictable for tests:
      - lowercase
      - keep \w (letters/digits/underscore)
      - collapse whitespace to single spaces
    """
    def _simple_norm(s: str) -> str:
        toks = re.findall(r"\w+", s.lower())
        return " ".join(toks)
    monkeypatch.setattr(S, "normalize_only", _simple_norm)
    yield


def test_corrects_2o_be_to_to_be_alpha_first_and_penalty():
    # 'to' is alphabetic & very frequent; '25' is numeric & rare.
    idx = FakeIndex({"to": 100, "be": 60, "25": 1})
    out = augment_query("2o be", idx)
    assert out["corrected"] == "to be"
    assert ("2o", "to", -5) in out["token_map"]
    assert out["total_penalty"] <= 0
    assert out["trailing_space"] is False


def test_preserves_trailing_space():
    idx = FakeIndex({"to": 100, "be": 60})
    out = augment_query("to be ", idx)
    assert out["corrected"].endswith(" ")
    assert out["total_penalty"] == 0


def test_prefers_higher_term_frequency_among_equal_edits():
    # Use a true Levenshtein-1 case (substitution), not a transposition.
    # "tge" is 1 substitution from both "the" and "toe" (pos 2).
    idx = FakeIndex({"the": 500, "toe": 50})
    out = augment_query("tge", idx)
    assert out["corrected"].strip() == "the"
    assert any(orig == "tge" and corr == "the" for orig, corr, _ in out["token_map"])


def test_or_knot_corrects_to_or_not():
    # Single-token 1-edit: delete 'k' at pos 1
    idx = FakeIndex({"or": 100, "not": 120})
    out = augment_query("or knot", idx)
    assert out["corrected"] == "or not"
    assert any(orig == "knot" and corr == "not" for orig, corr, _ in out["token_map"])
    assert out["total_penalty"] <= 0


def test_no_viable_1edit_corrections_leaves_query_unchanged():
    idx = FakeIndex({"alpha": 10, "beta": 8, "gamma": 5})
    out = augment_query("xyz", idx)
    assert out["corrected"].strip() == "xyz"
    assert out["total_penalty"] == 0


def test_numeric_token_without_letters_can_correct_numerically():
    # Token has no letters → numeric corrections allowed.
    idx = FakeIndex({"1234": 50, "123": 80, "124": 40})
    out = augment_query("1235", idx)
    assert out["corrected"].strip() in {"123", "1234", "124"}
    assert out["total_penalty"] <= 0
