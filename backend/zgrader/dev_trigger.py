"""Phase 1 dev entrypoint: run the full pipeline (preprocess -> analyze ->
compare -> PDF) against local sample images, without the watcher/API/portal.

    python -m zgrader.dev_trigger --front path/to/front.jpg --back path/to/back.jpg \\
        --game Pokemon --card-name "Charizard" --set-name "Base Set" --card-number 4/102
"""

import argparse
import secrets
import sys
from pathlib import Path

from zgrader.analysis import pipeline
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.db import SessionLocal
from zgrader.models import Card, ScanImage, ScanSide, Submission, SubmissionStatus, User, UserRole
from zgrader.reports import builder
from zgrader.scan_ingest import read_scan_metadata, sha256_file
from zgrader.seed import seed_all

_SAFE_DATABASE_SUFFIXES = ("_test", "_dev", "_local")


def refuse_unsafe_database(url: str) -> None:
    """Refuse to run against anything that isn't obviously a scratch database.

    This entrypoint creates users and runs the pipeline against whatever
    ZGRADER_DATABASE_URL names. On the development machine 127.0.0.1:5432 is an
    SSH tunnel to production, which looks identical to a local server, so the
    name is checked rather than the host.
    """
    from urllib.parse import urlsplit

    name = urlsplit(url).path.lstrip("/")
    if not name.endswith(_SAFE_DATABASE_SUFFIXES):
        raise RuntimeError(
            f"dev_trigger is refusing to run against database {name!r}. "
            f"Its name must end in one of {_SAFE_DATABASE_SUFFIXES}. This script creates "
            "users and runs the full pipeline, and 127.0.0.1:5432 on a development "
            "machine is often an SSH tunnel to production."
        )


def _get_or_create_user(db, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            is_verified=True,
            role=UserRole.client,
        )
        db.add(user)
        db.flush()
    return user


def run_dev_trigger(
    *,
    front_path: str,
    back_path: str | None,
    game: str,
    card_name: str,
    set_name: str | None = None,
    card_number: str | None = None,
    user_email: str = "dev@zgrader.local",
    submission_code: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        seed_all(db)

        user = _get_or_create_user(db, user_email)

        if submission_code is None:
            existing_count = db.query(Submission).count()
            submission_code = f"SUB-{existing_count + 1:05d}"

        submission = Submission(
            submission_code=submission_code, user_id=user.id, status=SubmissionStatus.created
        )
        db.add(submission)
        db.flush()

        db.add(
            Card(
                submission_id=submission.id,
                game=game,
                card_name=card_name,
                set_name=set_name,
                card_number=card_number,
            )
        )

        for side, path in ((ScanSide.front, front_path), (ScanSide.back, back_path)):
            if path is None:
                continue
            image_path = Path(path)
            width, height, dpi = read_scan_metadata(image_path)
            db.add(
                ScanImage(
                    submission_id=submission.id,
                    side=side,
                    file_path=str(image_path),
                    original_filename=image_path.name,
                    dpi=dpi,
                    width_px=width,
                    height_px=height,
                    checksum=sha256_file(image_path),
                )
            )
        db.flush()

        pipeline.run_analysis(db, submission)
        report = builder.generate_report(db, submission)
        db.commit()

        return {
            "submission_code": submission.submission_code,
            "status": submission.status.value,
            "report_pdf_path": report.pdf_path,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    refuse_unsafe_database(config.database_url)

    parser = argparse.ArgumentParser(
        description="Run the ZGrader analysis pipeline against local sample scans"
    )
    parser.add_argument("--front", required=True, help="Path to front scan image")
    parser.add_argument("--back", help="Path to back scan image")
    parser.add_argument(
        "--game", required=True, help="Game name, must match a CardDimensionReference.game"
    )
    parser.add_argument("--card-name", required=True)
    parser.add_argument("--set-name")
    parser.add_argument("--card-number")
    parser.add_argument("--user-email", default="dev@zgrader.local")
    parser.add_argument("--submission-code")
    args = parser.parse_args(argv)

    result = run_dev_trigger(
        front_path=args.front,
        back_path=args.back,
        game=args.game,
        card_name=args.card_name,
        set_name=args.set_name,
        card_number=args.card_number,
        user_email=args.user_email,
        submission_code=args.submission_code,
    )
    print(f"Submission {result['submission_code']} -> status={result['status']}")
    print(f"Report PDF: {result['report_pdf_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
