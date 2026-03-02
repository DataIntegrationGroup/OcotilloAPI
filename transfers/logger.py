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
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from services.gcs_helper import get_storage_bucket

_context = os.environ.get("OCO_LOG_CONTEXT", "transfer").strip().lower() or "transfer"

if _context == "cli":
    root = Path("cli") / "logs"
    _prefix = "cli"
else:
    root = Path("logs")
    if not os.getcwd().endswith("transfers"):
        root = Path("transfers") / root
    _prefix = "transfer"

root.mkdir(parents=True, exist_ok=True)

log_filename = f"{_prefix}_{datetime.now():%Y-%m-%dT%H_%M_%S}.log"
log_path = root / log_filename


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, mode="w", encoding="utf-8"),
    ],
    force=True,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ensure root logger propagates INFO level to handlers
logging.getLogger().setLevel(logging.INFO)

# workaround to not redirect httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)


def save_log_to_bucket():
    bucket = get_storage_bucket()
    bucket_folder = "transfer_logs" if _context != "cli" else "cli_logs"
    blob = bucket.blob(f"{bucket_folder}/{log_filename}")
    blob.upload_from_filename(log_path)
    logger.info(f"Uploaded log to gs://{bucket.name}/{bucket_folder}/{log_filename}")


# ============= EOF =============================================
