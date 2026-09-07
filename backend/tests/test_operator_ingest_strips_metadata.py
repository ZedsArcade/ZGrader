"""A file dropped into the scans directory is stripped like an upload.

Privacy policy section 4 tells customers: *"Every image is decoded and
re-encoded the moment it reaches us, which discards that metadata before
anything is written to disk."* That was true of `POST /submissions/{code}/scans`
and false of everything the watcher picks up, because `images.strip_metadata`
had exactly one call site and the watcher was not it.

It matters because of who the metadata belongs to. The operator path is for
cards customers post in, and an operator photographing one with a phone writes
their own GPS coordinates into the file. `GET /submissions/{code}/scans/{side}/raw`
then serves those original bytes to the account that owns the submission -- so
the customer could read the operator's location out of their own scan.

A flatbed carries no GPS, which is why this went unnoticed: the common case is
clean and the uncommon one leaks.
"""

import io

from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from zgrader.models import Submission, SubmissionStatus, User, UserRole
from zgrader.worker.watcher import _register_new_scans

#: 274 is Orientation, 34853 the GPS IFD pointer.
_ORIENTATION = 274
_GPS_IFD = 34853


def _portrait_card(width: int = 400, height: int = 560) -> Image.Image:
    """Unmistakably portrait, with a red stripe down the left edge so a
    rotation shows up in the pixels rather than only in the dimensions."""
    image = Image.new("RGB", (width, height), "white")
    for x in range(width // 10):
        for y in range(height):
            image.putpixel((x, y), (255, 0, 0))
    return image


def _as_a_phone_writes_it(upright: Image.Image) -> bytes:
    """A handset's output: pixels in sensor order, EXIF describing the
    correction, and GPS coordinates riding along in the same block.

    Orientation 6 means "rotate 270 to display", so the stored pixels are the
    upright image turned 90 the other way.
    """
    stored = upright.transpose(Image.ROTATE_90)

    exif = Image.Exif()
    exif[_ORIENTATION] = 6
    # The GPS block has to be built through get_ifd and populated with
    # IFDRational values. Assigning a plain dict of integer tuples raises
    # "bad operand type for abs()" deep inside Pillow's TIFF writer, which
    # reads as a bug in the test rather than a rejected coordinate format.
    gps = exif.get_ifd(_GPS_IFD)
    gps[1] = "N"
    gps[2] = (IFDRational(36), IFDRational(8), IFDRational(0))  # Gibraltar, near enough
    gps[3] = "W"
    gps[4] = (IFDRational(5), IFDRational(21), IFDRational(0))

    buffer = io.BytesIO()
    stored.save(buffer, format="JPEG", quality=95, subsampling=0, exif=exif)
    return buffer.getvalue()


def _submission_with_folder(db_session, code: str, email: str):
    """A submission and its scans folder, the way the operator drop path finds
    them: the folder exists because creating the submission made it."""
    from pathlib import Path

    from zgrader.config import config

    user = User(email=email, hashed_password="x", role=UserRole.client, is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code, user_id=user.id, status=SubmissionStatus.awaiting_scans
    )
    db_session.add(submission)
    db_session.commit()

    folder = Path(config.scans_dir) / code
    folder.mkdir(parents=True, exist_ok=True)
    return submission, folder


def test_the_fixture_really_carries_gps():
    """Guards the tests below from passing vacuously.

    If Pillow ever stops round-tripping the GPS block, every assertion about
    it being removed would still hold -- against a file that never had any.
    """
    raw = _as_a_phone_writes_it(_portrait_card())
    exif = Image.open(io.BytesIO(raw)).getexif()

    assert exif.get(_ORIENTATION) == 6, "fixture lost its orientation tag"
    assert exif.get_ifd(_GPS_IFD), "fixture carries no GPS, so it proves nothing"


def test_a_dropped_phone_photo_is_stored_without_its_metadata(db_session):
    submission, folder = _submission_with_folder(
        db_session, "SUB-98001", "operator-drop@example.com"
    )
    dropped = folder / "front.jpg"
    dropped.write_bytes(_as_a_phone_writes_it(_portrait_card()))

    _register_new_scans(db_session, submission, folder)

    with Image.open(dropped) as stored:
        exif = stored.getexif()
        assert not exif.get_ifd(_GPS_IFD), "the operator's GPS coordinates are still on disk"
        assert exif.get(_ORIENTATION) in (None, 1), "an orientation tag survived the rewrite"


def test_a_dropped_phone_photo_is_stored_upright(db_session):
    """Dropping the tag without applying it first would store the card on its
    side -- the failure `open_upright` exists to prevent on the upload path."""
    submission, folder = _submission_with_folder(
        db_session, "SUB-98002", "operator-upright@example.com"
    )
    dropped = folder / "front.jpg"
    dropped.write_bytes(_as_a_phone_writes_it(_portrait_card()))

    _register_new_scans(db_session, submission, folder)

    with Image.open(dropped) as stored:
        assert stored.height > stored.width, "stored sideways"


def test_the_recorded_row_describes_the_file_that_is_actually_on_disk(db_session):
    """Order matters: strip first, then measure.

    Dimensions, checksum and crop points are all recorded at registration. Read
    them before the rewrite and every one of them describes bytes that no
    longer exist -- and the checksum, whose whole job is detecting exactly
    that, would be the thing asserting it.
    """
    from zgrader.scan_ingest import sha256_file

    submission, folder = _submission_with_folder(
        db_session, "SUB-98003", "operator-checksum@example.com"
    )
    dropped = folder / "front.jpg"
    dropped.write_bytes(_as_a_phone_writes_it(_portrait_card()))

    _register_new_scans(db_session, submission, folder)
    # _register_new_scans flushes rather than commits -- its caller owns the
    # transaction -- so the row is only visible in this session.
    db_session.expire(submission, ["scan_images"])
    scan = submission.scan_images[0]

    assert scan.checksum == sha256_file(dropped), "checksum describes bytes that were replaced"
    with Image.open(dropped) as stored:
        assert (scan.width_px, scan.height_px) == stored.size, (
            "recorded dimensions are the pre-rewrite ones"
        )


def test_a_flatbed_scan_without_exif_still_registers(db_session):
    """The common case must keep working, and keep its pixels.

    A TIFF from a flatbed has no orientation and no GPS; the rewrite should be
    a no-op that leaves the image intact rather than something to route around.
    """
    submission, folder = _submission_with_folder(
        db_session, "SUB-98004", "operator-flatbed@example.com"
    )
    dropped = folder / "back.tiff"
    original = _portrait_card()
    original.save(dropped, format="TIFF")

    _register_new_scans(db_session, submission, folder)
    db_session.expire(submission, ["scan_images"])

    assert len(submission.scan_images) == 1, "a plain flatbed scan failed to register"
    with Image.open(dropped) as stored:
        assert stored.size == original.size
        assert stored.convert("RGB").getpixel((0, 0)) == (255, 0, 0), "the red edge was lost"


def test_an_unreadable_file_is_warned_about_rather_than_crashing_the_worker(db_session):
    """The worker processes every submission in a poll loop, so one bad file
    must not take the loop down with it."""
    submission, folder = _submission_with_folder(
        db_session, "SUB-98005", "operator-corrupt@example.com"
    )
    (folder / "front.jpg").write_bytes(b"this is not a JPEG")

    warnings = _register_new_scans(db_session, submission, folder)

    assert any("front.jpg" in w for w in warnings), f"no warning names the bad file: {warnings}"
    db_session.expire(submission, ["scan_images"])
    assert not submission.scan_images, "an unreadable file was registered as a scan"
