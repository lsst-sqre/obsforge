"""Declarative base for the ObsForge database schema."""

from typing import ClassVar

from sqlalchemy import DDL, Text, event
from sqlalchemy.orm import DeclarativeBase

__all__ = ["SchemaBase"]


class SchemaBase(DeclarativeBase):
    """SQLAlchemy declarative base for the ObsForge database schema."""

    type_annotation_map: ClassVar = {str: Text()}


event.listen(
    SchemaBase.metadata,
    "before_create",
    DDL("CREATE SCHEMA IF NOT EXISTS ivoa"),
)
