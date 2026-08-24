# ===============================================================================
# Copyright 2026 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
"""Free-text search on the geothermal well list query.

The UI well picker cannot offer the catalogue as a scrollable list, so it sends
a term and relies on the server to narrow it. These tests compile the query and
assert its shape, which needs no database.
"""

from services.geothermal_helper import get_geothermal_wells_query

# Columns `q` is matched against, by their legacy NM_Wells names.
SEARCH_COLUMNS = ("CurWellNam", "API", "CurWellNum", "CurOperatr", "County")


def compiled(**kwargs) -> str:
    sql = get_geothermal_wells_query(**kwargs)
    return str(sql.compile(compile_kwargs={"literal_binds": True}))


def test_no_search_term_adds_no_predicate():
    """An empty picker lists wells; it must not search for nothing."""
    baseline = compiled()

    assert compiled(q=None) == baseline
    assert compiled(q="") == baseline
    assert compiled(q="   ") == baseline
    assert "lower" not in baseline.lower() or "ilike" not in baseline.lower()


def test_term_matches_every_search_column():
    sql = compiled(q="jemez")

    for column in SEARCH_COLUMNS:
        assert column in sql, f"{column} is not searched"
    assert sql.lower().count("%jemez%") == len(SEARCH_COLUMNS)


def test_term_is_case_insensitive_substring():
    sql = compiled(q="jemez").lower()

    # ILIKE compiles to lower(...) LIKE lower(...) on some dialects; either way
    # the match is a substring wrapped in wildcards, not an equality.
    assert "%jemez%" in sql
    assert "like" in sql


def test_words_are_anded_so_each_one_narrows():
    """ "jemez 1" must be a subset of "jemez", not a union."""
    one_word = compiled(q="jemez")
    two_words = compiled(q="jemez 1")

    assert "%jemez%" in two_words
    assert "%1%" in two_words
    # A second word adds a second bracketed OR group rather than extending the
    # first, which is what makes the predicates AND together.
    assert two_words.count("OR") > one_word.count("OR")


def test_wildcards_in_the_term_are_escaped():
    """A stray % must not silently widen the search to the whole catalogue."""
    sql = compiled(q="50%")

    assert r"%50\%%" in sql
    assert "ESCAPE" in sql.upper()

    underscore = compiled(q="a_b")
    assert r"%a\_b%" in underscore


def test_search_composes_with_the_existing_filters():
    sql = compiled(q="jemez", county="Sandoval")

    assert "%jemez%" in sql
    assert "Sandoval" in sql
    # The geothermal flag is the base predicate and must survive.
    assert "GthrmExist" in sql


def test_results_stay_ordered_by_name():
    assert (
        compiled(q="jemez").rstrip().endswith('ORDER BY "NMW_WellHeaders"."CurWellNam"')
    )


# ============= EOF =============================================
