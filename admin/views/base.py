# ===============================================================================
# Copyright 2026
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

from typing import Any, Iterable, Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import InstrumentedAttribute
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import ExportType, action
from starlette_admin.contrib.sqla import ModelView

from db.engine import session_ctx


class OcotilloModelView(ModelView):
    """
    Shared admin behaviors for Ocotillo data models.

    - RBAC: admin can create/edit/delete; editor can edit; any authenticated user can view.
    - Data visibility: non-admin/editor users only see published rows when a release field exists.
    - Publish/Unpublish actions: toggle release status when enabled and a release field is present.
    """

    release_field = "release_status"
    draft_value = "draft"
    published_value = "published"
    enable_publish_actions: bool = True
    export_types: Sequence[ExportType] = (ExportType.CSV, ExportType.EXCEL)
    list_fields: Sequence[str] = ()
    field_labels: dict[str, str] | None = None
    field_help_texts: dict[str, str] | None = None

    def __init__(self, *args, **kwargs):
        model = args[0] if args else kwargs.get("model")
        if self.field_labels is None:
            self.field_labels = {}
        if self.field_help_texts is None:
            self.field_help_texts = {}
        if self.list_fields and model is not None:
            model_fields = [
                model.__dict__[key].key
                for key in list(model.__dict__.keys())
                if type(model.__dict__[key]) is InstrumentedAttribute
            ]
            self.exclude_fields_from_list = [
                name for name in model_fields if name not in self.list_fields
            ]
        super().__init__(*args, **kwargs)
        self._apply_field_overrides()

    def _apply_field_overrides(self) -> None:
        if not (self.field_labels or self.field_help_texts):
            return
        for field in self.fields:
            if field.name in self.field_labels:
                field.label = self.field_labels[field.name]
            if field.name in self.field_help_texts:
                field.help_text = self.field_help_texts[field.name]

    # ========= Permissions (RBAC) =========
    def _get_user(self, request: Request) -> Any:
        return getattr(request.state, "user", None)

    def _roles(self, request: Request) -> list[str]:
        user = self._get_user(request)
        return getattr(user, "roles", []) if user else []

    def _has_role(self, request: Request, roles: Iterable[str]) -> bool:
        return bool(set(self._roles(request)) & set(roles))

    def can_create(self, request: Request) -> bool:
        return self._has_role(request, {"admin"})

    def can_edit(self, request: Request) -> bool:
        return self._has_role(request, {"admin", "editor"})

    def can_delete(self, request: Request) -> bool:
        return self._has_role(request, {"admin"})

    def can_view_details(self, request: Request) -> bool:
        return self._get_user(request) is not None

    # ========= Data Visibility =========
    def get_list_query(self, request: Request):
        query = select(self.model)
        user = self._get_user(request)
        if user is None:
            # Return an empty result set for anonymous users
            return query.where(self.model.id == -1)

        if not hasattr(self.model, self.release_field):
            return query

        if self._has_role(request, {"admin", "editor"}):
            return query
        return query.where(
            getattr(self.model, self.release_field) == self.published_value
        )

    # ========= Actions (Publish / Unpublish) =========
    def _ensure_release_field(self) -> bool:
        return self.enable_publish_actions and hasattr(self.model, self.release_field)

    @action(
        name="publish_selected",
        text="Publish Selected",
        confirmation="Are you sure you want to publish the selected records?",
        submit_btn_text="Yes, publish",
        submit_btn_class="btn btn-success",
    )
    async def publish_selected(self, request: Request, pks: list[int]) -> Response:
        if not self._has_role(request, {"admin"}):
            return Response("Only admins can publish", status_code=403)
        if not self._ensure_release_field():
            return Response(
                "Publish action not available for this model", status_code=400
            )

        with session_ctx() as session:
            result = session.execute(
                update(self.model)
                .where(self.model.id.in_(pks))
                .values({self.release_field: self.published_value})
            )
            session.commit()
            updated_count = result.rowcount
        return Response(f"Published {updated_count} record(s)", status_code=200)

    @action(
        name="unpublish_selected",
        text="Unpublish Selected (set to draft)",
        confirmation="Are you sure you want to unpublish the selected records?",
        submit_btn_text="Yes, unpublish",
        submit_btn_class="btn btn-warning",
    )
    async def unpublish_selected(self, request: Request, pks: list[int]) -> Response:
        if not self._has_role(request, {"admin"}):
            return Response("Only admins can unpublish", status_code=403)
        if not self._ensure_release_field():
            return Response(
                "Unpublish action not available for this model", status_code=400
            )

        with session_ctx() as session:
            result = session.execute(
                update(self.model)
                .where(self.model.id.in_(pks))
                .values({self.release_field: self.draft_value})
            )
            session.commit()
            updated_count = result.rowcount
        return Response(f"Unpublished {updated_count} record(s)", status_code=200)


# ============= EOF =============================================
