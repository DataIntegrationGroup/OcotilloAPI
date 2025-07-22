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
from inspect import Signature, Parameter
from typing import Optional, List, Union, cast, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, OAuth2AuthorizationCodeBearer
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

TokenType = Union[str, HTTPAuthorizationCredentials]

scheme = OAuth2AuthorizationCodeBearer(
    # authorizationUrl=f"{settings.FIEF_URL}/authorize",
    # tokenUrl=f"{settings.FIEF_URL}/api/token",
    authorizationUrl="http://localhost:8000/authorize",
    tokenUrl="http://localhost:8000/api/token",
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
    # For now, we will just return True for demonstration purposes
    return True


# ============= EOF =============================================
