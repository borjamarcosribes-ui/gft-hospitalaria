"""Compatibility wrapper for the canonical backend ATC catalog.

New code should import app.services.atc_catalog_service directly. This module
remains so older imports keep resolving titles from the DB-backed backend seed
instead of from a duplicated frontend catalog.
"""

from app.services.atc_catalog_service import get_atc_title, get_atc_titles_map

ATC_TITLES = get_atc_titles_map()
