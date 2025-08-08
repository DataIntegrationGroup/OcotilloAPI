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
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import Base, Observation, Sample


def add_observation(session: Session, data: BaseModel) -> Base:

    if isinstance(data, BaseModel):
        data = data.model_dump(exclude_unset=True)

    # if 'thing_id' in data:
    #     thing_id = data.pop('thing_id')
    #     if 'sample_id' not in data:
    #         sample = Sample(thing_id=thing_id,
    #                         collection_method=data.get('collection_method', 'manual'),
    #                         collection_timestamp=data.get('observation_datetime'))
    #         session.add(sample)
    #         data['sample'] = sample
    #     else:
    #         raise ValueError('Cannot specify both thing_id and sample_id')

    obj = Observation(**data)

    session.add(obj)
    session.commit()
    session.refresh(obj)

    return obj


# ============= EOF =============================================
