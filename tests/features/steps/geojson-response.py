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

from behave import when, then


@when("the user requests all the wells as geojson")
def step_when_the_user_requests_all_the_wells_as_geojson(context):
    context.response = context.client.get(
        "/geospatial", params={"thing_type": "water well"}
    )


@then("the system should return a response in GEOJSON format")
def step_then_the_system_should_return_a_response_in_geojson_format(context):
    assert context.response.headers["Content-Type"] == "application/geo+json"


@then("the response should be a feature collection")
def step_then_the_response_should_be_a_feature_collection(context):
    assert context.response.json()["type"] == "FeatureCollection"


@then("the feature collection should have 3 features")
def step_then_the_feature_collection_should_have_3_features(context):
    assert len(context.response.json()["features"]) == 3


@when("the user requests all the wells for group Collabnet")
def step_when_the_user_requests_all_the_wells_for_group_collabnet(context):
    context.response = context.client.get("/geospatial", params={"group": "Collabnet"})


@then("the feature collection should have 2 features")
def step_then_the_feature_collection_should_have_2_features(context):
    obj = context.response.json()
    features = obj["features"]
    assert (
        len(features) == 2
    ), f"Unexpected number of features {len(features)}, features={features}"


# ============= EOF =============================================
