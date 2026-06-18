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
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

EditAction = Literal[
    "attachment_uploaded",
    "project_added",
    "project_removed",
    "record_updated",
    "record_created",
    "record_deleted",
]

NOTIFY_RESOURCE_TYPES = frozenset(
    {
        "well",
        "spring",
        "thing",
        "contact",
        "asset",
        "group",
        "location",
        "sensor",
        "sample",
    }
)

ACTION_HEADINGS: dict[EditAction, str] = {
    "attachment_uploaded": "Attachment uploaded",
    "project_added": "Project added",
    "project_removed": "Project removed",
    "record_updated": "Record updated",
    "record_created": "Record created",
    "record_deleted": "Record deleted",
}

RESOURCE_UI_PATHS: dict[str, str] = {
    "well": "ocotillo/well/show/{resource_id}",
    "spring": "ocotillo/spring/show/{resource_id}",
    "thing": "ocotillo/well/show/{resource_id}",
    "contact": "ocotillo/contact/show/{resource_id}",
    "group": "ocotillo/group/show/{resource_id}",
    "asset": "ocotillo/asset/show/{resource_id}",
    "location": "ocotillo/location/show/{resource_id}",
    "sensor": "ocotillo/sensor/show/{resource_id}",
    "sample": "ocotillo/sample/show/{resource_id}",
}


class EditEvent(BaseModel):
    action: EditAction
    resource_type: str
    resource_id: int | str
    resource_label: str
    summary: str
    field_changes: dict[str, dict[str, Any]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024**2):.1f} MB"


def environment_label(environment: str | None = None) -> str:
    raw = environment or os.environ.get("ENVIRONMENT", "unknown")
    env = raw.strip().lower()
    if env == "production":
        return "PRODUCTION"
    if env == "staging":
        return "STAGING"
    return env.upper() or "UNKNOWN"


def build_record_url(resource_type: str, resource_id: int | str) -> str | None:
    base = (os.environ.get("OCOTILLO_UI_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return None

    path_template = RESOURCE_UI_PATHS.get(resource_type)
    if not path_template:
        return None

    return f"{base}/{path_template.format(resource_id=resource_id)}"


def format_field_changes(
    field_changes: dict[str, dict[str, Any]] | None,
) -> str:
    if not field_changes:
        return ""

    lines: list[str] = []
    for field, change in field_changes.items():
        before = _format_display_value(change.get("before"))
        after = _format_display_value(change.get("after"))
        lines.append(f"{field}: {before} → {after}")
    return "\n".join(lines)


def build_slack_payload(
    event: EditEvent,
    user: dict[str, Any],
    environment: str | None = None,
) -> dict[str, Any]:
    env_label = environment_label(environment)
    heading_action = ACTION_HEADINGS.get(event.action, event.action)
    header = f"[{env_label}] {heading_action} — {event.resource_label}"

    actor_name = user.get("name") or user.get("preferred_username") or "Unknown"
    actor_email = user.get("email")
    who = actor_name if not actor_email else f"{actor_name} ({actor_email})"
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    fields: list[dict[str, str]] = [
        {"type": "mrkdwn", "text": f"*Who:*\n{who}"},
        {"type": "mrkdwn", "text": f"*When:*\n{when}"},
        {"type": "mrkdwn", "text": f"*What:*\n{event.summary}"},
    ]

    diff_text = format_field_changes(event.field_changes)
    if diff_text:
        fields.append({"type": "mrkdwn", "text": f"*Changes:*\n{diff_text}"})

    header_block = {
        "type": "header",
        "text": {"type": "plain_text", "text": header[:150]},
    }
    blocks: list[dict[str, Any]] = [
        header_block,
        {"type": "section", "fields": fields[:10]},
    ]

    record_url = build_record_url(event.resource_type, event.resource_id)
    if record_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{record_url}|View in Ocotillo →>",
                },
            }
        )

    return {"text": header, "blocks": blocks}


def notify_edit_event(user: Any, event: EditEvent) -> None:
    if not isinstance(user, dict):
        return

    webhook = os.environ.get("SLACK_EDITS_WEBHOOK_URL")
    if not webhook:
        return

    if event.resource_type not in NOTIFY_RESOURCE_TYPES:
        return

    payload = build_slack_payload(event, user)
    _post_slack_async(webhook, payload)


def _post_slack_async(webhook_url: str, payload: dict[str, Any]) -> None:
    def _send() -> None:
        try:
            httpx.post(webhook_url, json=payload, timeout=10.0)
        except Exception:
            logger.warning(
                "Slack edit notification failed",
                exc_info=True,
            )

    threading.Thread(target=_send, daemon=True).start()


def _format_display_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, str) and not value.strip():
        return "N/A"
    text = str(value)
    if len(text) > 200:
        return f"{text[:197]}..."
    return text


# ============= EOF =============================================
