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


# --- offsite ---------------------------------------------------------------
#
# The offsite step has one rule the local backup does not: it must never turn a
# good local backup into a failed run. It also has one refusal the local backup
# does not: it will not send customer data unencrypted. Both are shell logic,
# so both are testable here against stub rclone/age binaries.


def _offsite_rig(rig, *, remote="offsite:bucket", recipient="age1stubrecipient", age_ok=True,
                 rclone_ok=True):
    """Stub `age` and `rclone`, and record what they were asked to do."""
    calls = rig["tmp"] / "rclone-calls.txt"
    _stub(
        rig["bin"],
        "age",
        f"""
        # Real age reads stdin and writes ciphertext; the stub just marks it.
        printf 'ENCRYPTED:'
        cat
        exit {0 if age_ok else 1}
        """,
    )
    _stub(
        rig["bin"],
        "rclone",
        f"""
        echo "$@" >> "{_sh_path(calls)}"
        # rcat consumes stdin, as the real one does -- without this the
        # upstream `age` in the pipe gets SIGPIPE and the test measures the
        # wrong thing.
        if [ "$1" = "rcat" ]; then cat > /dev/null; fi
        exit {0 if rclone_ok else 1}
        """,
    )
    env = {
        "BACKUP_OFFSITE_REMOTE": remote,
        "BACKUP_AGE_RECIPIENT": recipient,
    }
    return calls, env


def _run_with(rig, extra_env) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PATH": f"{rig['bin']}{os.pathsep}{os.environ['PATH']}",
        "BACKUP_DIR": _sh_path(rig["backups"]),
        "BACKUP_DATA_DIR": _sh_path(rig["data"]),
        "POSTGRES_PASSWORD": "irrelevant",
        **extra_env,
    }
    return subprocess.run(
        [BASH, str(SCRIPT), "--once"], env=env, capture_output=True, text=True, timeout=60
    )


def test_nothing_is_sent_when_no_destination_is_configured(rig):
    """Shipping before the disk exists is a supported state. An operator who has
    not chosen a destination gets one quiet line, not a nightly failure."""
    _stub(rig["bin"], "pg_dump", 'printf "PGDMP-fake"\n')
    _stub(rig["bin"], "pg_restore", "exit 0\n")

    result = _run_with(rig, {})

    assert result.returncode == 0
    assert "keeping backups on this box only" in result.stdout
    assert list(rig["backups"].glob("db-*.dump"))


def test_a_configured_destination_receives_both_files_encrypted(rig):
    _stub(rig["bin"], "pg_dump", 'printf "PGDMP-fake"\n')
    _stub(rig["bin"], "pg_restore", "exit 0\n")
    calls, env = _offsite_rig(rig)

    result = _run_with(rig, env)

    assert result.returncode == 0, result.stderr
    sent = calls.read_text(encoding="utf-8")
    # The dump and the files archive, both as .age, plus the prune.
    assert "rcat offsite:bucket/db-" in sent and ".dump.age" in sent
    assert "rcat offsite:bucket/files-" in sent and ".tar.gz.age" in sent
    assert "delete --min-age 30d" in sent


def test_it_refuses_to_send_customer_data_unencrypted(rig):
    """What leaves here is card photographs and a dump of email addresses and
    password hashes. Sending that in the clear is a decision this script does
    not make silently -- and the local backup still has to succeed."""
    _stub(rig["bin"], "pg_dump", 'printf "PGDMP-fake"\n')
    _stub(rig["bin"], "pg_restore", "exit 0\n")
    calls, env = _offsite_rig(rig, recipient="")
    env["BACKUP_AGE_RECIPIENT"] = ""

    result = _run_with(rig, env)

    assert "refusing to send customer data unencrypted" in result.stderr
    assert not calls.exists(), "nothing should have been uploaded"
    assert list(rig["backups"].glob("db-*.dump")), "the local backup must still be good"
    assert result.returncode == 0, "an offsite refusal must not fail the local backup"


def test_an_offsite_failure_does_not_fail_the_local_backup(rig):
    """A dead network must not be reported as a backup problem. That is how a
    real failure gets lost among ignorable ones."""
    _stub(rig["bin"], "pg_dump", 'printf "PGDMP-fake"\n')
    _stub(rig["bin"], "pg_restore", "exit 0\n")
    _calls, env = _offsite_rig(rig, rclone_ok=False)

    result = _run_with(rig, env)

    assert result.returncode == 0
    assert "offsite copy did not complete" in result.stderr
    assert list(rig["backups"].glob("db-*.dump"))
    assert list(rig["backups"].glob("files-*.tar.gz"))


def test_a_failed_encryption_is_caught_rather_than_uploading_nothing(rig):
    """`age | rclone` without pipefail reports rclone's status, so a failing
    encrypt would look like a successful upload of an empty object."""
    _stub(rig["bin"], "pg_dump", 'printf "PGDMP-fake"\n')
    _stub(rig["bin"], "pg_restore", "exit 0\n")
    _calls, env = _offsite_rig(rig, age_ok=False)

    result = _run_with(rig, env)

    assert "could not send" in result.stderr
    assert result.returncode == 0, "the local backup is still good"


def test_nothing_is_sent_when_the_dump_itself_failed(rig):
    """Upload only what has been verified -- the same rule that governs
    rotation. A run that produced no good dump must reach the remote with
    nothing at all."""
    _stub(rig["bin"], "pg_dump", "exit 1\n")
    _stub(rig["bin"], "pg_restore", "exit 0\n")
    calls, env = _offsite_rig(rig)

    result = _run_with(rig, env)

    assert result.returncode == 1
    assert not calls.exists(), "a failed dump must not be uploaded"


# --- the drill's safety catch ---------------------------------------------


DRILL = Path(__file__).resolve().parents[2] / "infra" / "backup" / "drill.sh"


@pytest.mark.parametrize("name", ["zgrader", "zgrader_prod", "postgres"])
def test_the_drill_refuses_a_database_that_is_not_obviously_scratch(name):
    """It drops and recreates whatever it is pointed at, so the name guard is
    the only thing between a rehearsal and an outage. Same shape as the test
    suite's own refusal to run unless the database ends in `_test`."""
    result = subprocess.run(
        [BASH, str(DRILL)],
        env={**os.environ, "DRILL_DB": name},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert "refusing to run against" in result.stderr
