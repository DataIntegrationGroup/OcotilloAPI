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
import uuid
from typing import Any

from fastadmin import register, SqlAlchemyModelAdmin, WidgetType
from sqlalchemy import update, select

from db import async_database_sessionmaker
from db.base import User


@register(User, sqlalchemy_sessionmaker=async_database_sessionmaker)
class UserModelAdmin(SqlAlchemyModelAdmin):
    list_display = ("id", "username", "is_superuser")
    list_display_links = ("id", "username")
    list_filter = ("id", "username", "is_superuser")
    search_fields = ("username",)
    formfield_overrides = {  # noqa: RUF012
        "username": (WidgetType.SlugInput, {"required": True}),
        "password": (WidgetType.PasswordInput, {"passwordModalForm": True}),
        "avatar_url": (
            WidgetType.Upload,
            {
                "required": False,
                # Disable crop image for upload field
                # "disableCropImage": True,
            },
        ),
    }

    async def authenticate(
        self, username: str, password: str
    ) -> uuid.UUID | int | None:
        sessionmaker = self.get_sessionmaker()
        async with sessionmaker() as session:
            query = select(self.model_cls).filter_by(
                username=username, password=password, is_superuser=True
            )
            result = await session.scalars(query)
            obj = result.first()
            if not obj:
                return None
            return obj.id

    async def change_password(self, id: uuid.UUID | int, password: str) -> None:
        sessionmaker = self.get_sessionmaker()
        async with sessionmaker() as session:
            # use hash password for real usage
            query = (
                update(self.model_cls)
                .where(User.id.in_([id]))
                .values(password=password)
            )
            await session.execute(query)
            await session.commit()

    async def orm_save_upload_field(self, obj: Any, field: str, base64: str) -> None:
        sessionmaker = self.get_sessionmaker()
        async with sessionmaker() as session:
            # convert base64 to bytes, upload to s3/filestorage, get url and save or save base64 as is to db (don't recomment it)
            query = (
                update(self.model_cls)
                .where(User.id.in_([obj.id]))
                .values(**{field: base64})
            )
            await session.execute(query)
            await session.commit()


# ============= EOF =============================================
