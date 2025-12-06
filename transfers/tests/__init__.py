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

from dotenv import load_dotenv

load_dotenv(override=True)

# for safety dont test on the production database port
os.environ["POSTGRES_PORT"] = "54321"

from core.initializers import erase_and_rebuild_db


erase_and_rebuild_db()
# ============= EOF =============================================
