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
"""Public data disclaimer page.

Both pygeoapi mounts advertise this URL as
`metadata.identification.terms_of_service`, so it is deliberately
unauthenticated -- an OGC client following the advertised link has no
credentials to present.

HTML is the default because the pygeoapi landing page renders
terms_of_service as a link a human clicks; JSON is offered for catalog
harvesters that want the text as data rather than markup.
"""

import html
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from core.disclaimer import (
    DISCLAIMER_CONTACT_EMAIL,
    DISCLAIMER_PARAGRAPHS,
    DISCLAIMER_TITLE,
)

router = APIRouter(tags=["disclaimer"])

_STYLE = (
    "max-width:44rem;margin:3rem auto;padding:0 1.25rem;"
    "font-family:system-ui,-apple-system,'Segoe UI',sans-serif;"
    "line-height:1.6;color:#1a1a1a"
)


def _wants_json(request: Request, f: str | None) -> bool:
    # An explicit ?f= wins over content negotiation, matching pygeoapi's own
    # precedence so the two surfaces behave the same way.
    if f is not None:
        return f.lower() == "json"
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


def _render_html() -> str:
    paragraphs = []
    for paragraph in DISCLAIMER_PARAGRAPHS:
        escaped = html.escape(paragraph)
        escaped = escaped.replace(
            DISCLAIMER_CONTACT_EMAIL,
            f'<a href="mailto:{DISCLAIMER_CONTACT_EMAIL}">'
            f"{DISCLAIMER_CONTACT_EMAIL}</a>",
        )
        paragraphs.append(f"    <p>{escaped}</p>")
    body = "\n".join(paragraphs)
    title = html.escape(DISCLAIMER_TITLE)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="utf-8">\n'
        '    <meta name="viewport" content="width=device-width, '
        'initial-scale=1">\n'
        f"    <title>{title} | Ocotillo</title>\n"
        "  </head>\n"
        f'  <body style="{_STYLE}">\n'
        f"    <h1>{title}</h1>\n"
        f"{body}\n"
        "  </body>\n"
        "</html>\n"
    )


@router.get(
    "/disclaimer",
    response_class=HTMLResponse,
    summary="Data disclaimer and terms of service",
    responses={
        200: {
            "content": {"text/html": {}, "application/json": {}},
            "description": "The disclaimer as HTML (default) or JSON (?f=json).",
        }
    },
)
def get_disclaimer(
    request: Request,
    f: Annotated[
        str | None,
        Query(description="Response format. Use 'json' for the text as data."),
    ] = None,
):
    if _wants_json(request, f):
        return JSONResponse(
            {
                "title": DISCLAIMER_TITLE,
                "paragraphs": list(DISCLAIMER_PARAGRAPHS),
                "contact": DISCLAIMER_CONTACT_EMAIL,
            }
        )
    return HTMLResponse(_render_html())
