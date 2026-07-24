"""Declarative base for the ObsForge database schema."""

from typing import ClassVar

from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase

__all__ = ["SchemaBase"]


class SchemaBase(DeclarativeBase):
    """SQLAlchemy declarative base for the ObsForge database schema."""

    type_annotation_map: ClassVar = {str: Text()}
