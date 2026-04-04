"""
Services d'authentification JWT.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.contracts.auth import UserLoginRequest, UserRegisterRequest
from backend.core.saas_config import saas_settings
from backend.core.security import create_access_token, hash_password, verify_password
from backend.models.user import User


class AuthService:
    """
    Gere creation de compte, login et lecture de l'utilisateur courant.
    """

    def register_user(self, db_session: Session, payload: UserRegisterRequest) -> User:
        existing_user = (
            db_session.query(User).filter(User.email == payload.email.lower()).first()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un utilisateur existe deja avec cet email.",
            )

        user = User(
            email=payload.email.lower(),
            full_name=payload.full_name.strip(),
            hashed_password=hash_password(payload.password),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def authenticate_user(
        self,
        db_session: Session,
        payload: UserLoginRequest,
    ) -> tuple[User, str]:
        user = db_session.query(User).filter(User.email == payload.email.lower()).first()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou mot de passe invalide.",
            )

        token = create_access_token(str(user.id))
        return user, token

    def get_user_from_token(self, db_session: Session, token: str) -> User:
        try:
            payload = jwt.decode(
                token,
                saas_settings.jwt_secret_key,
                algorithms=[saas_settings.jwt_algorithm],
            )
        except JWTError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide ou expire.",
            ) from error

        subject = payload.get("sub")
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token JWT incomplet.",
            )

        user = db_session.query(User).filter(User.id == int(subject)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur introuvable.",
            )

        return user

