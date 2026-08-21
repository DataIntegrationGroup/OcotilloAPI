"""Reference data has to load before the seed touches it.

Migrations insert a handful of lexicon terms of their own, so "the table has
rows" says nothing about whether core/lexicon.json was ever loaded.
"""

import contextlib

import pytest
from sqlalchemy import func, select

from core.initializers import init_parameter
from db.engine import session_ctx
from db.parameter import Parameter
from transfers import seed as seed_module
from transfers.seed import (
    REQUIRED_LEXICON_CATEGORIES,
    assert_lexicon_ready,
    ensure_seed_prereqs,
    get_terms_by_category,
)


def test_ensure_seed_prereqs_loads_reference_data_even_when_tables_have_rows(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        "core.initializers.init_lexicon", lambda: calls.append("lexicon")
    )
    monkeypatch.setattr(
        "core.initializers.init_parameter", lambda: calls.append("parameter")
    )

    ensure_seed_prereqs()

    assert calls == ["lexicon", "parameter"]


def test_assert_lexicon_ready_names_the_empty_categories(monkeypatch):
    empty = {"organization", "note_type"}

    @contextlib.contextmanager
    def fake_session_ctx():
        yield object()

    monkeypatch.setattr(seed_module, "session_ctx", fake_session_ctx)
    monkeypatch.setattr(
        seed_module,
        "get_terms_by_category",
        lambda _session, category: [] if category in empty else ["term"],
    )

    with pytest.raises(RuntimeError) as excinfo:
        assert_lexicon_ready()

    message = str(excinfo.value)
    assert "organization" in message
    assert "note_type" in message
    assert "sample_method" not in message


def test_required_categories_have_terms_after_reference_data_loads():
    with session_ctx() as session:
        empty = [
            category
            for category in REQUIRED_LEXICON_CATEGORIES
            if not get_terms_by_category(session, category)
        ]

    assert empty == []


def test_init_parameter_leaves_existing_parameters_alone():
    with session_ctx() as session:
        before = session.scalar(select(func.count()).select_from(Parameter))

    init_parameter()

    with session_ctx() as session:
        after = session.scalar(select(func.count()).select_from(Parameter))

    assert after == before
