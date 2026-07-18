"""Phase 1 dev entrypoint: run the full pipeline (preprocess -> analyze ->
compare -> PDF) against local sample images, without the watcher/API/portal.

    python -m zgrader.dev_trigger --front path/to/front.jpg --back path/to/back.jpg \\
        --game Pokemon --card-name "Charizard" --set-name "Base Set" --card-number 4/102
"""

import argparse
import hashlib
import sys
from pathlib import Path

from PIL import Image

from zgrader.analysis import pipeline
from zgrader.config import config
from zgrader.db import SessionLocal
from zgrader.models import Card, ScanImage, ScanSide, Submission, SubmissionStatus, User, UserRole
from zgrader.reports import builder
from zgrader.seed import seed_all


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_metadata(path: Path) -> tuple[int, int, int]:
    with Image.open(path) as img:
        width, height = img.size
        dpi_info = img.info.get("dpi")
        dpi = int(round(dpi_info[0])) if dpi_info else config.default_scan_dpi
    return width, height, dpi


def _get_or_create_user(db, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password="dev-trigger-no-auth",
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
            width, height, dpi = _scan_metadata(image_path)
            db.add(
                ScanImage(
                    submission_id=submission.id,
                    side=side,
                    file_path=str(image_path),
                    original_filename=image_path.name,
                    dpi=dpi,
                    width_px=width,
                    height_px=height,
                    checksum=_sha256(image_path),
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
