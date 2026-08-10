"""infra/backup/backup.sh, exercised against stub pg_* binaries.

The database half of that script is hard to get wrong -- it is one pg_dump
call. The parts that decide whether a backup is trustworthy are all shell:
a partial dump must never be renamed into place, rotation must never run after
a failure, and an unreadable dump must be reported rather than counted. Those
are testable without Postgres, and they are the ones worth testing.

Skipped where bash is unavailable, which is most Windows checkouts unless Git
Bash is on PATH.
"""

import os
import shutil
import subprocess
import tarfile
import textwrap
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "backup" / "backup.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")


def _sh_path(path: Path) -> str:
    """A path bash and tar will both accept.

    GNU tar treats `C:/backups/x.tar.gz` as a *remote host* spec -- the colon
    means host:path, as in rsh -- and fails with "Child returned status 128".
    Converting to the MSYS form (/c/backups/...) keeps the script itself free
    of a flag it would only ever need on a platform it does not run on.
    """
    text = str(path).replace("\\", "/")
    if len(text) > 1 and text[1] == ":":
        return f"/{text[0].lower()}{text[2:]}"
    return text


def _stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/usr/bin/env bash\n{textwrap.dedent(body)}", encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture()
def rig(tmp_path):
    """A scratch backup destination, some data to archive, and stub pg_*
    binaries that behave however a given test needs."""
    bin_dir = tmp_path / "bin"
    backups = tmp_path / "backups"
    data = tmp_path / "data"
    for directory in (bin_dir, backups, data / "reports", data / "scans"):
        directory.mkdir(parents=True)
    (data / "reports" / "report.pdf").write_text("pretend pdf", encoding="utf-8")
    (data / "scans" / "front.png").write_text("pretend scan", encoding="utf-8")

    _stub(bin_dir, "pg_isready", "exit 0\n")
    return {"bin": bin_dir, "backups": backups, "data": data, "tmp": tmp_path}


def _run(rig) -> subprocess.CompletedProcess:
    """One backup, via the script's --once mode.

    The service loops forever by design, so the first version of this killed
    it after a few seconds -- which hung, because bash's `sleep` child inherits
    the stdout pipe and keeps it open after bash dies. --once exists partly for
    that reason and partly because taking a backup before a risky change is
    something an operator wants anyway.
    """
    env = {
        **os.environ,
        "PATH": f"{rig['bin']}{os.pathsep}{os.environ['PATH']}",
        "BACKUP_DIR": _sh_path(rig["backups"]),
        "BACKUP_DATA_DIR": _sh_path(rig["data"]),
        "POSTGRES_PASSWORD": "irrelevant",
    }
    return subprocess.run(
        [BASH, str(SCRIPT), "--once"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_a_good_run_writes_a_dump_and_an_archive(rig):
    _stub(rig["bin"], "pg_dump", "echo 'PGDMP pretend dump contents'\n")
    _stub(rig["bin"], "pg_restore", "exit 0\n")

    result = _run(rig)
    output = result.stdout + result.stderr

    dumps = list(rig["backups"].glob("db-*.dump"))
    archives = list(rig["backups"].glob("files-*.tar.gz"))
    assert len(dumps) == 1, output
    assert len(archives) == 1, output
    assert "OK --" in output


def test_an_unreadable_dump_is_not_counted_as_a_backup(rig):
    """The classic failure: pg_dump exits 0 having written something useless.
    Verifying with pg_restore --list turns that into a nightly log line
    instead of a discovery made during a restore."""
    _stub(rig["bin"], "pg_dump", "echo 'not really a dump'\n")
    _stub(rig["bin"], "pg_restore", "exit 1\n")

    result = _run(rig)
    output = result.stdout + result.stderr

    assert list(rig["backups"].glob("db-*.dump")) == [], "an unreadable dump was accepted"
    # Left for inspection rather than deleted -- the operator needs to see it.
    assert list(rig["backups"].glob("*.partial")), output
    assert "FAILED" in output


def test_a_failed_dump_leaves_earlier_backups_alone(rig):
    """Rotation must never run after a failure, or a run of broken nights
    quietly eats the last good backup."""
    old = rig["backups"] / "db-20200101T000000Z.dump"
    old.write_text("an older backup", encoding="utf-8")
    # Older than any plausible retention window.
    ancient = time.time() - 400 * 86400
    os.utime(old, (ancient, ancient))

    _stub(rig["bin"], "pg_dump", "exit 1\n")
    _stub(rig["bin"], "pg_restore", "exit 0\n")

    result = _run(rig)
    output = result.stdout + result.stderr

    assert old.exists(), f"rotation ran after a failed dump: {output}"
    assert "FAILED" in output


def test_rotation_removes_only_what_is_past_retention(rig):
    _stub(rig["bin"], "pg_dump", "echo 'PGDMP pretend dump contents'\n")
    _stub(rig["bin"], "pg_restore", "exit 0\n")

    stale = rig["backups"] / "db-20200101T000000Z.dump"
    stale.write_text("stale", encoding="utf-8")
    ancient = time.time() - 400 * 86400
    os.utime(stale, (ancient, ancient))

    recent = rig["backups"] / "db-20991231T000000Z.dump"
    recent.write_text("recent", encoding="utf-8")

    result = _run(rig)
    output = result.stdout + result.stderr

    assert not stale.exists(), f"stale backup survived rotation: {output}"
    assert recent.exists(), f"a recent backup was rotated out: {output}"


def test_it_still_backs_up_the_database_with_no_reports_or_scans_yet(rig):
    """A deployment with no submissions has neither directory. Refusing to
    back up the database because nobody has uploaded a card would be absurd."""
    shutil.rmtree(rig["data"] / "reports")
    shutil.rmtree(rig["data"] / "scans")
    _stub(rig["bin"], "pg_dump", "echo 'PGDMP pretend dump contents'\n")
    _stub(rig["bin"], "pg_restore", "exit 0\n")

    result = _run(rig)
    output = result.stdout + result.stderr

    assert len(list(rig["backups"].glob("db-*.dump"))) == 1, output
    assert list(rig["backups"].glob("files-*.tar.gz")) == []
    assert "OK --" in output


def test_the_archive_contains_both_trees(rig):
    _stub(rig["bin"], "pg_dump", "echo 'PGDMP pretend dump contents'\n")
    _stub(rig["bin"], "pg_restore", "exit 0\n")

    _run(rig)

    archive = next(iter(rig["backups"].glob("files-*.tar.gz")))
    # tarfile rather than shelling out to tar, for the same drive-letter
    # reason _sh_path exists.
    with tarfile.open(archive) as handle:
        names = handle.getnames()
    assert any(name.startswith("reports") for name in names), names
    assert any(name.startswith("scans") for name in names), names
