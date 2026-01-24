"""
SEO-friendly region slug mapping for region-first URLs.

Single source of truth:
- REGION_SLUG_MAP: slug -> Octopus region code (e.g. "london" -> "C")

Region codes/names are reused from Config.OCTOPUS_REGION_NAMES.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from app.config import Config


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


# Slug -> region code mapping (derived from existing region name source of truth).
REGION_SLUG_MAP: Dict[str, str] = {
    _slugify(region_name): region_code
    for region_code, region_name in Config.OCTOPUS_REGION_NAMES.items()
}

# Reverse mapping for convenience.
REGION_CODE_TO_SLUG: Dict[str, str] = {code: slug for slug, code in REGION_SLUG_MAP.items()}

if len(REGION_SLUG_MAP) != len(Config.OCTOPUS_REGION_NAMES):
    raise ValueError("Region slug collision detected; slugs must be unique.")


def region_code_from_slug(region_slug: str) -> Optional[str]:
    if not region_slug:
        return None
    return REGION_SLUG_MAP.get(region_slug.strip().lower())


def region_slug_from_code(region_code: str) -> Optional[str]:
    if not region_code:
        return None
    return REGION_CODE_TO_SLUG.get(region_code.strip().upper())


def region_name_from_code(region_code: str) -> Optional[str]:
    if not region_code:
        return None
    return Config.OCTOPUS_REGION_NAMES.get(region_code.strip().upper())

