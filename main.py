import os

from fastapi_pagination import add_pagination

os.environ["ADMIN_USER_MODEL"] = "User"
os.environ["ADMIN_USER_MODEL_USERNAME_FIELD"] = "username"
os.environ["ADMIN_SECRET_KEY"] = "secret"

from starlette.middleware.cors import CORSMiddleware

from core.app import app

from fastadmin import fastapi_app as admin_app

from api.base import router as base_router
from api.form import router as form_router
from api.timeseries import router as timeseries_router
from api.lexicon import router as lexicon_router
from api.chemisty import router as chemistry_router
from api.geothermal import router as geothermal_router
from api.collabnet import router as collabnet_router
from api.geochronology import router as geochronology_router
from api.publication import router as publication_router
from api.author import router as author_router
from api.asset import router as asset_router

app.include_router(base_router)
app.include_router(form_router)
app.include_router(timeseries_router)
app.include_router(lexicon_router)
app.include_router(chemistry_router)
app.include_router(geothermal_router)
app.include_router(collabnet_router)
app.include_router(geochronology_router)
app.include_router(publication_router)
app.include_router(author_router)
app.include_router(asset_router)

from admin.user import *
from admin.base import *
app.mount("/admin", admin_app)


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
