"""The unauthenticated face of a shared report.

Nothing here takes a token in the Authorization sense -- the share token in the
path *is* the credential, and it is the only one. Two consequences run through
every route below:

* **Everything answers 404**, never 403. A 403 tells somebody probing tokens
  that they found one, which is precisely the bit they were missing.
* **`submission_code` never appears in a URL.** It names the directory the files
  live in, so it is resolved from the token server-side and goes no further.
  Codes come from a sequence and are guessable; that is the whole reason this
  feature has a token at all.

The payload is built by `schemas.public_report.build_public_report`, which maps
field by field rather than serialising the ORM row. See that module for why.
"""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from zgrader import sharing
from zgrader.api.ratelimit import rate_limit
from zgrader.api.routers.catalog import _active_grading_companies
from zgrader.config import config
from zgrader.db import get_db
from zgrader.schemas.public_report import PublicReportOut, build_public_report

router = APIRouter(prefix="/public/reports", tags=["public"])

#: Generous. Cloudflare absorbs the normal case entirely; this exists so a
#: scraper that misses cache cannot sit on a home server running OpenCV.
_RATE_LIMIT = 120
_RATE_WINDOW_SECONDS = 60

#: Filenames the pipeline writes per side, as `{side}_{kind}.png` in
#: reports/{code}/. Matched against a pattern rather than globbed, so a request
#: can only ever name a file this pipeline produces.
_SIDES = ("front", "back")
_IMAGE_KIND_RE = re.compile(r"^(base|centering|(centering|corners|edges|surface)_[a-z0-9_]+_crop)$")


def _image_response(submission, filename: str) -> FileResponse:
    path = Path(config.reports_dir) / submission.submission_code / filename
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    # Cached hard at the edge. The token is the only thing in the URL and a
    # rotation issues a new one, so a stale cache entry belongs to a URL that no
    # longer resolves rather than to a link somebody revoked -- the image cannot
    # outlive its own address.
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/{token}",
    response_model=PublicReportOut,
    dependencies=[Depends(rate_limit("public_report", _RATE_LIMIT, _RATE_WINDOW_SECONDS))],
)
def get_public_report(token: str, db: Session = Depends(get_db)) -> PublicReportOut:
    submission = sharing.resolve_shared_submission(token, db)
    return build_public_report(submission, _active_grading_companies(db))


@router.get(
    "/{token}/og.png",
    dependencies=[Depends(rate_limit("public_og", _RATE_LIMIT, _RATE_WINDOW_SECONDS))],
)
def get_public_og_image(token: str, db: Session = Depends(get_db)) -> FileResponse:
    """The link preview image, at a stable name.

    A fixed address so the OG tag does not have to know which files this
    submission happens to have -- and so the crawler fetching it (Discord,
    WhatsApp, Reddit) gets a plain cacheable PNG with no token header, which is
    the only kind of fetch those crawlers make.
    """
    submission = sharing.resolve_shared_submission(token, db)
    return _image_response(submission, "front_base.png")


@router.get(
    "/{token}/images/{side}_{kind}.png",
    dependencies=[Depends(rate_limit("public_image", _RATE_LIMIT, _RATE_WINDOW_SECONDS))],
)
def get_public_image(
    token: str, side: str, kind: str, db: Session = Depends(get_db)
) -> FileResponse:
    """One analysed image for a shared report.

    The path ends in `.png` on purpose: Cloudflare's default cache keys off the
    extension, so these are cached at the edge with no cache rule to configure.

    `side` and `kind` are both validated against closed sets before anything
    touches disk. The submission code is never supplied by the caller, so the
    directory is not something a request can steer.
    """
    if side not in _SIDES or not _IMAGE_KIND_RE.match(kind):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    submission = sharing.resolve_shared_submission(token, db)
    return _image_response(submission, f"{side}_{kind}.png")
