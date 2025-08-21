import os
import sentry_sdk

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
    send_default_pii=True,
)


from fastapi_pagination import add_pagination

from starlette.middleware.cors import CORSMiddleware

from core.app import app

from api.group import router as group_router
from api.contact import router as contact_router
from api.location import router as location_router
from api.thing import router as thing_router
from api.sensor import router as sensor_router

# from api.series import router as series_router
from api.sample import router as sample_router
from api.observation import router as observation_router

# from api.form import router as form_router

from api.lexicon import router as lexicon_router

from api.geothermal import router as geothermal_router
from api.geochronology import router as geochronology_router
from api.publication import router as publication_router
from api.author import router as author_router
from api.asset import router as asset_router
from api.search import router as search_router
from api.geospatial import router as geospatial_router

app.include_router(asset_router)
app.include_router(author_router)
app.include_router(contact_router)
app.include_router(geochronology_router)
app.include_router(geospatial_router)
app.include_router(geothermal_router)
app.include_router(group_router)
app.include_router(lexicon_router)
app.include_router(location_router)
app.include_router(observation_router)
app.include_router(publication_router)
app.include_router(sample_router)
app.include_router(sensor_router)
app.include_router(search_router)
app.include_router(thing_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, adjust as needed for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# setup pagination
add_pagination(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
