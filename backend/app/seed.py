from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import DEMO_COURSES
from app.config import Settings
from app.models import Course, OperatorProfile
from app.security import hash_password

logger = logging.getLogger(__name__)


def seed_all(session: Session, settings: Settings) -> None:
    _seed_courses(session)
    if settings.auth_adapter == "demo":
        _seed_demo_operators(session, settings)


def _seed_courses(session: Session) -> None:
    for item in DEMO_COURSES:
        existing = session.execute(select(Course).where(Course.slug == item.slug)).scalar_one_or_none()
        if existing:
            continue
        session.add(
            Course(
                slug=item.slug,
                name=item.name,
                description=item.description,
                contents=item.contents,
                requirements=item.requirements,
                modality=item.modality,
                duration=item.duration,
                schedule=item.schedule,
                price_amount=item.price_amount,
                price_currency=item.price_currency,
                authorized_link=item.authorized_link,
                active=True,
                is_fictional_demo=True,
                search_aliases=item.search_aliases,
            )
        )
    session.flush()


def _upsert_operator(session: Session, email: str, name: str, password: str, auth_user_id: str) -> None:
    existing = session.execute(select(OperatorProfile).where(OperatorProfile.email == email)).scalar_one_or_none()
    if existing:
        if not existing.password_hash:
            existing.password_hash = hash_password(password)
        existing.enabled = True
        existing.display_name = name
        return
    session.add(
        OperatorProfile(
            auth_user_id=auth_user_id,
            email=email,
            display_name=name,
            role="operator",
            enabled=True,
            password_hash=hash_password(password),
        )
    )


def _seed_demo_operators(session: Session, settings: Settings) -> None:
    _upsert_operator(
        session,
        settings.demo_operator_email,
        settings.demo_operator_name,
        settings.demo_operator_password,
        "demo-operator-a",
    )
    _upsert_operator(
        session,
        settings.demo_operator_b_email,
        settings.demo_operator_b_name,
        settings.demo_operator_b_password,
        "demo-operator-b",
    )
    logger.info("Seeded configured operator profiles for local authentication")
