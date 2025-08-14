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
# import os
from inspect import Signature, Parameter
from typing import Optional, List, Union, cast, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, OAuth2AuthorizationCodeBearer
from jwt.algorithms import RSAAlgorithm
from starlette import status
from starlette.requests import Request
from starlette.responses import Response
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from jose.exceptions import JWTError
import httpx

AUTHENTIK_ISSUER = os.environ.get('AUTHENTIK_URL')
JWKS_URL = f"{AUTHENTIK_ISSUER}jwks/"
ALGORITHMS = ["RS256"]

# Fetch JWKS (could also cache this)
def get_jwks():
    resp = httpx.get(JWKS_URL)
    resp.raise_for_status()
    return resp.json()

jwks = get_jwks()

def get_public_key(token):
    unverified_header = jwt.get_unverified_header(token)
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            return RSAAlgorithm.from_jwk(key)
    raise HTTPException(status_code=401, detail="Invalid signing key")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


TokenType = Union[str, HTTPAuthorizationCredentials]
scheme = OAuth2AuthorizationCodeBearer(
    # authorizationUrl=f"{settings.FIEF_URL}/authorize",
    # tokenUrl=f"{settings.FIEF_URL}/api/token",
    authorizationUrl=os.environ.get("AUTHENTIK_AUTHORIZE_URL"),
    tokenUrl=os.environ.get("AUTHENTIK_TOKEN_URL"),
    scopes={"openid": "openid", "offline_access": "offline_access"},
    auto_error=False,
)


def authenticated(
    optional: bool = False,
    scope: Optional[List[str]] = None,
    permissions: Optional[List[str]] = None,
):

    def _authenicated(
        request: Request,
        response: Response,
        token: TokenType = Depends(cast(Callable, scheme)),
    ):
        # def _authenicated(request: Request, response: Response):
        # def _authenicated():
        """
        A placeholder for the authentication logic.
        This function should check if the user is authenticated and has the required permissions.
        If `optional` is True, it should allow unauthenticated access.
        """
        if optional and not token:
            return True

        # Here you would typically check the token against your authentication system
        # and verify the user's permissions.

        if not token or not verify_token(token, scope, permissions):
            response.status_code = status.HTTP_401_UNAUTHORIZED

        # this is a placeholder for the actual authentication logic
        return True

    return _authenicated



def verify_token(
    token: TokenType, scope: Optional[List[str]], permissions: Optional[List[str]]
) -> bool:
    """
    Placeholder function to verify the token.
    This should contain the logic to check if the token is valid and has the required permissions.
    """
    # Implement your token verification logic here

    payload = _get_token_payload(token)

    # Optionally check scopes and permissions in payload
    if scope:
        if not all(s in payload.get("scope", []) for s in scope):
            return False
    if permissions:
        if not all(p in payload.get("groups", []) for p in permissions):
            return False
    return True


def _get_token_payload(token: str = Depends(oauth2_scheme)):
    try:
        public_key = get_public_key(token)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=ALGORITHMS,
            audience=os.environ.get("AUTHENTIK_CLIENT_ID"),  # Must match Authentik application
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )



# ============= EOF =============================================
