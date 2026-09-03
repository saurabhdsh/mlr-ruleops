#!/usr/bin/env python3
"""Generate additional synthetic historical reviews for larger demos."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("SEED_ON_STARTUP", "false")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", type=int, default=2000)
    args = parser.parse_args()

    from app.db.session import SessionLocal
    from app.db.seed import generate_historical_reviews

    db = SessionLocal()
    try:
        created = generate_historical_reviews(db, args.reviews)
        db.commit()
        print(f"Created {created} synthetic historical reviews")
    finally:
        db.close()


if __name__ == "__main__":
    main()
