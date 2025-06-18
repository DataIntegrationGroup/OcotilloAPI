# ===============================================================================
# Copyright 2025 ross
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
from routes.regex import QUERY_REGEX


def test_query_regex_eq():
    text = "visible eq true"
    match = QUERY_REGEX.match(text)
    assert match is not None
    assert match.group("field") == "visible"
    assert match.group("value") == "true"
    assert match.group("operator") == "eq"


def test_query_regex_ne():
    text = "visible ne true"
    match = QUERY_REGEX.match(text)
    assert match is not None
    assert match.group("field") == "visible"
    assert match.group("value") == "true"
    assert match.group("operator") == "ne"


def test_query_regex_nested():
    text = "well.api_id eq '1001-0001'"
    match = QUERY_REGEX.match(text)
    assert match is not None
    assert match.group("field") == "well.api_id"
    assert match.group("value") == "'1001-0001'"
    assert match.group("operator") == "eq"


def test_query_regex_nested_between():
    text = "well.well_depth between [500,1000]"
    match = QUERY_REGEX.match(text)
    assert match is not None
    assert match.group("field") == "well.well_depth"
    assert match.group("value") == "[500,1000]"
    assert match.group("operator") == "between"


def test_query_regex_like():
    text = "construction_notes like '%test%'"
    match = QUERY_REGEX.match(text)
    assert match is not None
    assert match.group("field") == "construction_notes"
    assert match.group("value") == "'%test%'"
    assert match.group("operator") == "like"


# ============= EOF =============================================
