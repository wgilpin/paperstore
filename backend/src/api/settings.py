"""API router for managing user settings."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.setting import Setting
from src.schemas.setting import SettingsSchema

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_auth(request: Request) -> None:
    """Require an authenticated user session."""
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/settings", response_model=SettingsSchema, dependencies=[Depends(_require_auth)])
def get_settings(db: Session = Depends(get_session)) -> SettingsSchema:
    """Get all settings."""
    about_me = db.query(Setting).filter(Setting.key == "about_me").first()
    return SettingsSchema(about_me=about_me.value if about_me else "")


@router.put("/settings", response_model=SettingsSchema, dependencies=[Depends(_require_auth)])
def update_settings(
    body: SettingsSchema,
    db: Session = Depends(get_session),
) -> SettingsSchema:
    """Create or update user settings."""
    about_me = db.query(Setting).filter(Setting.key == "about_me").first()
    value = body.about_me or ""
    if about_me is None:
        about_me = Setting(key="about_me", value=value)
        db.add(about_me)
    else:
        about_me.value = value
    db.commit()
    return SettingsSchema(about_me=about_me.value)
