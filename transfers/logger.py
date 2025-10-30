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

# class StreamToLogger:
#     def __init__(self, logger_, level):
#         self.logger = logger_
#         self.level = level
#         self.linebuf = ""
#
#     def write(self, buf):
#         for line in buf.rstrip().splitlines():
#             self.logger.log(self.level, line.rstrip())
#
#     def flush(self):
#         pass
root = Path("logs")
if not os.getcwd().endswith("transfers"):
    root = Path("transfers") / root

if not os.path.exists(root):
    os.mkdir(root)

log_filename = root / f"transfer_{datetime.now():%Y-%m-%dT%Hh%Mm%Ss}.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename, mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# workaround to not redirect httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)

# redirect stderr to the logger
# sys.stderr = StreamToLogger(logger, logging.ERROR)


def save_log_to_bucket():
    bucket = get_storage_bucket()
    blob = bucket.blob(f"transfer_logs/{log_filename}")
    blob.upload_from_filename(log_filename)
    logger.info(f"Uploaded log to gs://{bucket.name}/transfer_logs/{log_filename}")


# ============= EOF =============================================
