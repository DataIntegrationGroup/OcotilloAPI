# Edit notifications and the activity log (Epic 6)

BDMS-921 adds Slack notifications when Ocotillo data is edited. Epic 6 (activity log) will persist the same events for in-app history. This document describes how the two fit together.

## Current state (BDMS-921)

Mutations in the OcotilloAPI service layer call `notify_edit_event(user, event)` from `services/edit_notification_helper.py`.

- `EditEvent` carries action, resource type/id/label, summary, optional field diffs, and metadata.
- When `SLACK_EDITS_WEBHOOK_URL` is set, the helper posts a Block Kit message to Slack in a background thread.
- When the webhook is unset (local dev), or `user` is not a dict (auth disabled in tests), notification is a no-op.
- Failures are logged and never fail the HTTP request.

Wired today:

| Action | Where |
|--------|--------|
| `attachment_uploaded` | `api/asset.py` `upload_and_record_asset` (new uploads only) |
| `project_added` / `project_removed` | `services/group_helper.py` |
| `record_created` / `record_updated` / `record_deleted` | `services/crud_helper.py` |

## Future state (Epic 6.1)

Epic 6 introduces an `ActivityLog` table and a service helper, roughly:

```python
def log_activity(
    session,
    actor,
    action,
    resource_type,
    resource_id,
    *,
    resource_label=None,
    field_changes=None,
    metadata=None,
):
    # persist ActivityLog row (not built yet)
    notify_edit_event(
        actor,
        EditEvent(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_label=resource_label or f"ID {resource_id}",
            summary=_activity_summary(...),
            field_changes=field_changes,
            metadata=metadata or {},
        ),
    )
```

### Migration path

1. **Keep `EditEvent` as the shared event shape** so Slack payloads and the activity log UI read the same fields (`actor`, `action`, `resource_*`, `field_changes`, `metadata`).
2. **Move call sites from `notify_edit_event` to `log_activity`** as Epic 6.1 lands. `log_activity` writes to PostgreSQL first, then calls `notify_edit_event` as a side effect.
3. **Retire direct `notify_edit_event` calls** in route handlers and one-off helpers once those paths go through `log_activity`.
4. **Map action names** between Slack labels and Epic 6 enums where they differ (e.g. `project_added` → activity log `update` with metadata describing the project change).

### Field diffs

`model_patcher` already computes `{field: {before, after}}` for Slack. Epic 6 stores the same JSON on `ActivityLog.field_changes`. No second diff format is needed.

### Exclusions (unchanged)

- `POST /feedback` keeps its own Slack webhook.
- Transfer scripts, bulk imports, and non-user mutations should not call `log_activity` or `notify_edit_event`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `SLACK_EDITS_WEBHOOK_URL` | Incoming webhook for edit notifications (Secret Manager in deployed envs) |
| `OCOTILLO_UI_BASE_URL` | UI origin for deep links in Slack messages |
| `ENVIRONMENT` | `staging` or `production`; prefixed in Slack headers |

See `.env.example` for local defaults.
