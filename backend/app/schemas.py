from typing import Any, Optional
from pydantic import BaseModel, EmailStr, field_validator


class MarketplaceCreate(BaseModel):
    displayName: str
    ownerName: str
    ownerEmail: str


class MarketplaceUpdate(BaseModel):
    displayName: Optional[str] = None
    ownerName: Optional[str] = None
    ownerEmail: Optional[str] = None


class MarketplaceOut(BaseModel):
    slug: str
    displayName: str
    ownerName: str
    ownerEmail: str
    createdAt: int
    updatedAt: int
    skillCount: Optional[int] = None


class SkillCreate(BaseModel):
    displayName: str
    description: str
    content: str


class SkillUpdate(BaseModel):
    displayName: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class SkillOut(BaseModel):
    marketplaceSlug: str
    slug: str
    displayName: str
    description: str
    version: str
    content: Optional[str] = None
    createdAt: int
    updatedAt: int
    lastCommit: Optional[str] = None
