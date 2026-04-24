from fastapi import Depends

from .database import get_db


def get_current_user() -> dict[str, str]:
    return {"id": "placeholder-user"}


def get_db_dependency(db=Depends(get_db)):
    return db
