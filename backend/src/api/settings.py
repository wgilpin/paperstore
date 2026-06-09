"""API router for managing user settings."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.db import get_session
from src.models.setting import Setting
from src.schemas.setting import SettingsSchema

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/settings", response_model=SettingsSchema)
def get_settings(db: Session = Depends(get_session)) -> SettingsSchema:
    """Get all settings."""
    about_me = db.query(Setting).filter(Setting.key == "about_me").first()
    return SettingsSchema(about_me=about_me.value if about_me else "")


@router.put("/settings", response_model=SettingsSchema)
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
