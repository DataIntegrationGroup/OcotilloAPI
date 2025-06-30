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
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from db import Base, AutoBaseMixin


class Asset(Base, AutoBaseMixin):
    # name = Column(String(100), nullable=False, unique=True)
    # file_type = Column(String(50), nullable=False)
    #
    # content = Column(UploadedFileField)
    # photo = Column(UploadedFileField(upload_type=UploadedImageWithThumb))

    filename = Column(String)
    storage_service = Column(String)
    storage_path = Column(String)
    mime_type = Column(String)
    size = Column(Integer)


class AssetLocationAssociation(Base, AutoBaseMixin):

    asset_id = Column(
        Integer, ForeignKey("asset.id", ondelete="CASCADE"), nullable=False
    )
    location_id = Column(
        Integer, ForeignKey("sample_location.id", ondelete="CASCADE"), nullable=False
    )

    location = relationship("SampleLocation", back_populates="asset_associations")

    # publication = relationship("Publication", back_populates="author_associations")
    # author = relationship("Author", back_populates="publication_associations")


# ============= EOF =============================================
