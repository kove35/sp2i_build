"""
Routes SaaS d'authentification.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.contracts.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from backend.db.session import get_db_session
from backend.saas_services.auth_service import AuthService


router = APIRouter(prefix="/saas/auth", tags=["SaaS Auth"])
auth_service = AuthService()
bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db_session: Session = Depends(get_db_session),
):
    """
    Resolve l'utilisateur courant a partir du bearer token.
    """
    return auth_service.get_user_from_token(db_session, credentials.credentials)


@router.post("/register", response_model=TokenResponse)
def register_user(
    payload: UserRegisterRequest,
    db_session: Session = Depends(get_db_session),
) -> TokenResponse:
    user = auth_service.register_user(db_session, payload)
    _, token = auth_service.authenticate_user(
        db_session,
        UserLoginRequest(email=payload.email, password=payload.password),
    )
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: UserLoginRequest,
    db_session: Session = Depends(get_db_session),
) -> TokenResponse:
    user, token = auth_service.authenticate_user(db_session, payload)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def read_current_user(user=Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)

