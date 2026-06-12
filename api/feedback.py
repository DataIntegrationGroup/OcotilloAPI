import os
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from core.dependencies import viewer_dependency

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    type: Literal["bug", "feature"]
    page_url: str
    reporter_name: str | None = None
    reporter_email: str | None = None
    browser: str | None = None
    submitted_at: str | None = None
    # Bug fields
    what_happened: str | None = None
    severity: str = "Low"
    # Feature fields
    problem: str | None = None
    who_would_use: str | None = None
    what_it_should_do: str | None = None


class FeedbackResponse(BaseModel):
    jira_key: str
    jira_url: str


def _build_jira_payload(payload: FeedbackCreate) -> dict:
    project = os.environ.get("JIRA_DEFAULT_PROJECT", "BDMS")

    reporter_line = payload.reporter_name or payload.reporter_email or "Unknown"
    submitted = payload.submitted_at or datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    context_items = [
        {
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": f"Page: {payload.page_url}"}],
                }
            ],
        },
        {
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"Reported by: {reporter_line}"}
                    ],
                }
            ],
        },
        {
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Browser: {payload.browser or 'Unknown'}",
                        }
                    ],
                }
            ],
        },
        {
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": f"Submitted: {submitted}"}],
                }
            ],
        },
    ]

    if payload.type == "bug":
        summary = f"Bug: {(payload.what_happened or '')[:80].strip()}"
        issue_type = "Bug"
        body_content = [
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "What happened"}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": payload.what_happened or ""}],
            },
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Severity"}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": payload.severity}],
            },
        ]
        priority_map = {"Low": "Low", "Medium": "Medium", "High": "High"}
        priority = priority_map.get(payload.severity, "Medium")
    else:
        summary = f"Feature request: {(payload.problem or '')[:80].strip()}"
        issue_type = "Task"
        body_content = [
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "What problem does this solve?"}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": payload.problem or ""}],
            },
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Who would use this?"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": payload.who_would_use or "Not specified"}
                ],
            },
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "What should it do?"}],
            },
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": payload.what_it_should_do or ""}],
            },
        ]
        priority = "Medium"

    description = {
        "type": "doc",
        "version": 1,
        "content": [
            *body_content,
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Context"}],
            },
            {"type": "bulletList", "content": context_items},
        ],
    }

    return {
        "fields": {
            "project": {"key": project},
            "issuetype": {"name": issue_type},
            "summary": summary,
            "description": description,
            "priority": {"name": priority},
        }
    }


def _build_slack_payload(payload: FeedbackCreate, jira_key: str, jira_url: str) -> dict:
    reporter = payload.reporter_name or payload.reporter_email or "Unknown"
    submitted = payload.submitted_at or datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    if payload.type == "bug":
        header = f"🐛 Bug report — {jira_key}"
        description_text = payload.what_happened or ""
        severity_field = {"type": "mrkdwn", "text": f"*Severity:*\n{payload.severity}"}
        extra_fields = [severity_field]
    else:
        header = f"💡 Feature request — {jira_key}"
        description_text = payload.problem or ""
        extra_fields = []
        if payload.who_would_use:
            extra_fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Who would use this:*\n{payload.who_would_use}",
                }
            )

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Reporter:*\n{reporter}"},
                {"type": "mrkdwn", "text": f"*Submitted:*\n{submitted}"},
                {"type": "mrkdwn", "text": f"*Page:*\n{payload.page_url}"},
                *extra_fields,
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": description_text[:2900]},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{jira_url}|View {jira_key} in JIRA →>",
            },
        },
    ]

    return {"text": header, "blocks": blocks}


@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    payload: FeedbackCreate,
    _user=viewer_dependency,
):
    jira_base = os.environ["JIRA_BASE_URL"]
    jira_email = os.environ["JIRA_EMAIL"]
    jira_token = os.environ["JIRA_API_TOKEN"]

    async with httpx.AsyncClient() as client:
        jira_resp = await client.post(
            f"{jira_base}/rest/api/3/issue",
            json=_build_jira_payload(payload),
            auth=(jira_email, jira_token),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        jira_resp.raise_for_status()
        jira_data = jira_resp.json()

    jira_key = jira_data["key"]
    jira_url = f"{jira_base}/browse/{jira_key}"

    slack_webhook = os.environ.get("SLACK_FEEDBACK_WEBHOOK_URL")
    if slack_webhook:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    slack_webhook,
                    json=_build_slack_payload(payload, jira_key, jira_url),
                    timeout=10,
                )
        except Exception:
            # Slack notification is best-effort — don't fail the request if it errors
            pass

    return FeedbackResponse(jira_key=jira_key, jira_url=jira_url)


# ============= EOF =============================================
