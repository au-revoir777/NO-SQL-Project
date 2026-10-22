"""User management shared by the API, the CLI and demo seeding."""

from __future__ import annotations

import os

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fraudsim.api.v1.auth.security import hash_password
from fraudsim.appdb.models import Role, User

logger = structlog.get_logger(__name__)
MIN_PASSWORD_LENGTH = 12


class UserError(ValueError):
    pass


def normalise_email(email: str) -> str:
    return email.strip().lower()


def find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == normalise_email(email)))


def create_user(db: Session, email: str, password: str, role: Role, display_name: str = "") -> User:
    email = normalise_email(email)
    if "@" not in email:
        raise UserError("email must contain @")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise UserError(f"password must have at least {MIN_PASSWORD_LENGTH} characters")
    if find_by_email(db, email) is not None:
        raise UserError(f"a user with email {email} already exists")
    user = User(
        email=email,
        display_name=display_name or email.split("@")[0],
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        token_version=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_demo_users(db: Session) -> list[str]:
    """
    Create the demo accounts named in DEMO_ADMIN_EMAIL/PASSWORD and
    DEMO_ANALYST_EMAIL/PASSWORD, if set and not present yet. Never from code or git.
    """
    created = []
    for prefix, role in (("DEMO_ADMIN", Role.ADMIN), ("DEMO_ANALYST", Role.ANALYST)):
        email = os.environ.get(f"{prefix}_EMAIL")
        password = os.environ.get(f"{prefix}_PASSWORD")
        if not email or not password:
            continue
        if find_by_email(db, email) is not None:
            continue
        create_user(db, email, password, role, display_name=f"Demo {role.value}")
        created.append(normalise_email(email))
        logger.info("seeded demo user", email=normalise_email(email), role=role.value)
    return created
