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
from __future__ import annotations

import importlib
import pkgutil

from data_migrations.base import DataMigration


def _discover_migration_modules() -> list[str]:
    base_pkg = __name__.rsplit(".", 1)[0]
    migrations_pkg = f"{base_pkg}.migrations"
    try:
        package = importlib.import_module(migrations_pkg)
    except ModuleNotFoundError:
        return []
    package_paths = list(getattr(package, "__path__", []))
    modules: list[str] = []
    for module_info in pkgutil.iter_modules(package_paths):
        if module_info.ispkg:
            continue
        if module_info.name.startswith("_"):
            continue
        modules.append(f"{migrations_pkg}.{module_info.name}")
    return modules


def list_migrations() -> list[DataMigration]:
    migrations: list[DataMigration] = []
    for module_path in _discover_migration_modules():
        module = importlib.import_module(module_path)
        migration = getattr(module, "MIGRATION", None)
        if migration is None:
            continue
        if not isinstance(migration, DataMigration):
            raise TypeError(f"{module_path}.MIGRATION must be a DataMigration instance")
        migrations.append(migration)
    return migrations


def get_migration(migration_id: str) -> DataMigration | None:
    for migration in list_migrations():
        if migration.id == migration_id:
            return migration
    return None
