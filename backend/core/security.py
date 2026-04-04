"""
Utilitaires de securite :
- hash mot de passe
- JWT
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from backend.core.saas_config import saas_settings


password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Transforme un mot de passe en hash securise.
    """
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare un mot de passe brut avec son hash.
    """
    return password_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """
    Cree un token JWT d'acces.
    """
    expire_at = datetime.now(timezone.utc) + timedelta(
        minutes=saas_settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire_at}
    return jwt.encode(
        payload,
        saas_settings.jwt_secret_key,
        algorithm=saas_settings.jwt_algorithm,
    )
