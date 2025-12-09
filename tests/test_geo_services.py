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
import pytest

from services.util import (
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)


@pytest.mark.xfail(reason="Relies on an outside service")
def test_quad_name_from_point():
    x = -106.904107
    y = 34.068198
    quad = get_quad_name_from_point(x, y)
    assert quad == "Socorro"


@pytest.mark.xfail(reason="Relies on an outside service")
def test_state_name_from_point():
    x = -100.904107
    y = 34.068198
    state = get_state_from_point(x, y)
    assert state == "Texas"


@pytest.mark.xfail(reason="Relies on an outside service")
def test_county_name_from_point():
    x = -106.904107
    y = 34.068198
    county = get_county_from_point(x, y)
    assert county == "Socorro"


@pytest.mark.xfail(reason="Relies on an outside service")
def test_quad_name_from_point_bad_point():
    x = 1.904107
    y = 34.068198
    quad = get_quad_name_from_point(x, y)
    assert quad is None


@pytest.mark.xfail(reason="Relies on an outside service")
def test_state_name_from_point_bad_point():
    x = 1.904107
    y = 34.068198
    state = get_state_from_point(x, y)
    assert state is None


@pytest.mark.xfail(reason="Relies on an outside service")
def test_county_name_from_point_bad_point():
    x = 1.904107
    y = 34.068198
    county = get_county_from_point(x, y)
    assert county is None


# ============= EOF =============================================
