import importlib

from domain.lithology import LITHOLOGY_CODES, lithology_code


def test_lithology_code_reverses_term():
    assert lithology_code("Clay, yellow") == "CLYE"
    assert lithology_code("Gravel, cemented") == "GRCM"


def test_lithology_code_ignores_case_and_whitespace():
    assert lithology_code("  clay, YELLOW ") == "CLYE"


def test_lithology_code_unknown_or_blank_is_none():
    assert lithology_code("Not a lithology") is None
    assert lithology_code("") is None
    assert lithology_code(None) is None


def test_lithology_codes_are_one_to_one():
    terms = [t.casefold() for t in LITHOLOGY_CODES.values()]
    assert len(terms) == len(set(terms))


def test_lithology_codes_match_backfill_table():
    # The backfill resolved codes to terms with its own frozen copy. The
    # NGWMN export reverses that mapping, so the two must stay identical.
    backfill = importlib.import_module(
        "data_migrations.migrations.20261105_0001_backfill_stratigraphic_intervals"
    )
    assert LITHOLOGY_CODES == backfill.LU_LITHOLOGY
