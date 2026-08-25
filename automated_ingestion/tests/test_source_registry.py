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
"""Registry behavior: duplicate keys are a bug, not a silent overwrite."""

import pytest

from automated_ingestion.shared import source_registry
from automated_ingestion.shared.source_registry import SourceDefinition


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    monkeypatch.setattr(source_registry, "_SOURCES", {})


def _definition(key="san_acacia"):
    return SourceDefinition(
        key=key,
        display_name="San Acacia Reach",
        dataset_name="raw_sanacaciareach",
    )


def test_registered_source_is_retrievable():
    source_registry.register(_definition())
    assert source_registry.get_source("san_acacia").display_name == "San Acacia Reach"


def test_duplicate_key_is_rejected():
    source_registry.register(_definition())
    with pytest.raises(ValueError, match="already registered"):
        source_registry.register(_definition())


def test_unknown_key_raises():
    with pytest.raises(KeyError, match="san_acacia"):
        source_registry.get_source("san_acacia")


def test_all_sources_is_sorted_by_key():
    source_registry.register(_definition("van_essen"))
    source_registry.register(_definition("bernco"))
    assert [s.key for s in source_registry.all_sources()] == ["bernco", "van_essen"]


# ============= EOF =============================================
