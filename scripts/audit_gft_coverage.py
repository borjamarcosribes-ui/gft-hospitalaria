"""Print GFT canonical coverage audit as JSON.

Usage:
    python -m scripts.audit_gft_coverage
"""
import json

from app.core.database import SessionLocal
from app.services.gft_canonical_payload_service import audit_gft_coverage


def main() -> None:
    db = SessionLocal()
    try:
        print(json.dumps(audit_gft_coverage(db), ensure_ascii=False, default=str, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
