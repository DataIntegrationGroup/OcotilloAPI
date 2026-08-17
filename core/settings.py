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
import os
from importlib.metadata import PackageNotFoundError, version as _pkg_version


def _resolve_version() -> str:
    env = os.getenv("APP_VERSION")
    if env:
        return env.removeprefix("v")
    try:
        return _pkg_version("OcotilloAPI")
    except PackageNotFoundError:
        return "0.0.0"


class Settings:
    version = _resolve_version()

    @property
    def mode(self) -> str:
        """Deployment mode, read fresh from the environment on every access.

        This used to be snapshotted in __init__. Settings() is instantiated
        while core.app is imported, which happens before core.factory calls
        load_dotenv() -- so whether MODE was visible depended on which module
        happened to call load_dotenv() first. Reading it lazily makes the
        value independent of import order, which matters because
        core.permissions gates the authentication bypass on it.
        """
        return os.getenv("MODE", "")

    def get_enum(self, name: str):
        if name == "MODE":
            return self.mode
        else:
            raise ValueError(f"Unknown setting: {name}")


settings = Settings()
# ============= EOF =============================================
