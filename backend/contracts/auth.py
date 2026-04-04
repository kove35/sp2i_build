"""
Schemas d'authentification JWT.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """
    Charge utile pour creer un utilisateur SaaS.
    """

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=6, max_length=255)


class UserLoginRequest(BaseModel):
    """
    Charge utile de connexion.
    """

    email: EmailStr
    password: str = Field(min_length=6, max_length=255)


class UserResponse(BaseModel):
    """
    Representation publique d'un utilisateur.
    """

    id: int
    email: str
    full_name: str
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """
    Reponse standard JWT.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserResponse

