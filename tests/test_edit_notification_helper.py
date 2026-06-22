import pytest

from services.edit_notification_helper import (
    EditEvent,
    build_record_url,
    build_slack_payload,
    environment_label,
    format_field_changes,
    format_file_size,
    notify_edit_event,
)


@pytest.fixture
def slack_capture(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def _capture(webhook_url: str, payload: dict) -> None:
        calls.append((webhook_url, payload))

    monkeypatch.setenv("SLACK_EDITS_WEBHOOK_URL", "https://hooks.slack.test/edit")
    monkeypatch.setenv("OCOTILLO_UI_BASE_URL", "https://ocotillo.example.org")
    monkeypatch.setattr(
        "services.edit_notification_helper._post_slack_async",
        _capture,
    )
    return calls


def test_environment_label():
    assert environment_label("staging") == "STAGING"
    assert environment_label("production") == "PRODUCTION"
    assert environment_label("dev") == "DEV"


def test_format_file_size():
    assert format_file_size(512) == "512 B"
    assert format_file_size(2048) == "2.0 KB"
    assert format_file_size(2 * 1024 * 1024) == "2.0 MB"


def test_build_record_url(monkeypatch):
    monkeypatch.setenv("OCOTILLO_UI_BASE_URL", "https://ocotillo.example.org")
    assert (
        build_record_url("well", 42)
        == "https://ocotillo.example.org/ocotillo/well/show/42"
    )
    assert build_record_url("unknown", 1) is None


def test_build_slack_payload_includes_environment_and_diffs(monkeypatch):
    monkeypatch.setenv("OCOTILLO_UI_BASE_URL", "https://ocotillo.example.org")
    event = EditEvent(
        action="record_updated",
        resource_type="contact",
        resource_id=7,
        resource_label="Jane Doe",
        summary="Updated contact Jane Doe",
        field_changes={
            "phone": {"before": "505-555-1234", "after": "505-555-5678"},
        },
    )
    user = {"name": "Jeremy Zilar", "email": "jeremy@example.org"}

    payload = build_slack_payload(event, user, environment="staging")
    header = payload["blocks"][0]["text"]["text"]

    assert header.startswith("[STAGING] Record updated — Jane Doe")
    assert payload["blocks"][1]["fields"][0]["text"].startswith("*Who:*")
    assert "505-555-1234" in payload["blocks"][1]["fields"][3]["text"]
    assert "View in Ocotillo" in payload["blocks"][2]["text"]["text"]


def test_format_field_changes_empty():
    assert format_field_changes(None) == ""
    assert format_field_changes({}) == ""


def test_build_slack_payload_attachment_upload():
    event = EditEvent(
        action="attachment_uploaded",
        resource_type="well",
        resource_id=28251,
        resource_label="NM-28251",
        summary=(
            "Uploaded construction_log.pdf (application/pdf, 1.2 MB) " "to NM-28251"
        ),
    )
    payload = build_slack_payload(
        event,
        {"name": "Tyler Smith", "email": "tyler@example.org"},
        environment="production",
    )

    assert payload["blocks"][0]["text"]["text"].startswith(
        "[PRODUCTION] Attachment uploaded — NM-28251"
    )


def test_notify_edit_event_skips_without_webhook(monkeypatch, slack_capture):
    monkeypatch.delenv("SLACK_EDITS_WEBHOOK_URL", raising=False)
    notify_edit_event(
        {"name": "Test User"},
        EditEvent(
            action="project_added",
            resource_type="well",
            resource_id=1,
            resource_label="NM-1",
            summary='Added NM-1 to project "Demo"',
        ),
    )
    assert slack_capture == []


def test_notify_edit_event_skips_non_dict_user(slack_capture):
    notify_edit_event(
        True,
        EditEvent(
            action="project_added",
            resource_type="well",
            resource_id=1,
            resource_label="NM-1",
            summary='Added NM-1 to project "Demo"',
        ),
    )
    assert slack_capture == []


def test_notify_edit_event_posts_payload(slack_capture):
    notify_edit_event(
        {"name": "Test User", "email": "test@example.org"},
        EditEvent(
            action="project_removed",
            resource_type="well",
            resource_id=99,
            resource_label="NM-99",
            summary='Removed NM-99 from project "Demo"',
        ),
    )

    assert len(slack_capture) == 1
    webhook, payload = slack_capture[0]
    assert webhook == "https://hooks.slack.test/edit"
    assert "project_removed" not in payload["text"]
    assert "NM-99" in payload["text"]
