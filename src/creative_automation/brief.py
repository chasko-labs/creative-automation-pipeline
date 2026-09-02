"""Brief schema — validates JSON/YAML campaign briefs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class ProductBrief(BaseModel):
    id: str = Field(description="slug id, used as folder name e.g. hydrating-serum")
    name: str
    description: Optional[str] = None
    hero_asset: Optional[str] = None  # explicit path override


class CampaignBrief(BaseModel):
    campaign_name: str = Field(default="campaign")
    brand: str = Field(default="Aura")
    products: List[ProductBrief]
    target_region: str = Field(description="e.g. US, FR, JP, BR")
    target_market: Optional[str] = Field(default=None, description="alias for region")
    target_audience: str
    campaign_message: str
    localized_messages: Optional[dict[str, str]] = Field(default=None, description="region -> message")
    brand_colors: Optional[List[str]] = Field(default=None, description="hex colors e.g. #0A2540")
    language: str = Field(default="en")

    @field_validator("products")
    @classmethod
    def at_least_two(cls, v):
        if len(v) < 2:
            raise ValueError("at least two products required")
        return v

    @property
    def region(self) -> str:
        return self.target_market or self.target_region


def load_brief(path: str | Path) -> CampaignBrief:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        # try yaml then json
        try:
            data = yaml.safe_load(text)
        except Exception:
            data = json.loads(text)
    return CampaignBrief.model_validate(data)
