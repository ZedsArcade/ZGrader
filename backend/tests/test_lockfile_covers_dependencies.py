"""Every declared dependency must appear in the lock the image builds from.

The Dockerfile installs `-r requirements.lock --require-hashes` and then the
package itself with `--no-deps`. That combination is what makes a build
reproducible, and it is also what makes a stale lock dangerous: adding a
dependency to pyproject.toml without regenerating the lock produces an image
where the new import simply is not installed. `--no-deps` means pip will not
quietly fetch it, so the failure surfaces at runtime, in the container, as an
ImportError on a code path nobody exercised during review.

This is the same guard as test_compose_env_coverage.py, for the same class of
mistake: two files that must agree, with nothing but memory keeping them in
step.
"""

import re
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PYPROJECT = BACKEND / "pyproject.toml"
LOCKFILE = BACKEND / "requirements.lock"


def _normalise(name: str) -> str:
    """PEP 503 normalisation -- `opencv_python_headless` and
    `opencv-python-headless` are the same project."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared_dependencies() -> set[str]:
    """Project names from pyproject, minus version specifiers and extras.

    `uvicorn[standard]>=0.32` is the awkward one: the extra decides whether
    uvloop and httptools come along, but the name to look for in the lock is
    still `uvicorn`.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    names = set()
    for spec in data["project"]["dependencies"]:
        name = re.split(r"[<>=!~\[;\s]", spec, maxsplit=1)[0]
        if name:
            names.add(_normalise(name))
    return names


def _locked_packages() -> set[str]:
    names = set()
    for line in LOCKFILE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9._-]+)==", line)
        if match:
            names.add(_normalise(match.group(1)))
    return names


def test_the_lockfile_exists():
    assert LOCKFILE.is_file(), (
        "backend/requirements.lock is missing -- the Dockerfile installs from it, "
        "so the image cannot build without it."
    )


def test_every_declared_dependency_is_locked():
    missing = sorted(_declared_dependencies() - _locked_packages())
    assert not missing, (
        f"Declared in pyproject.toml but absent from requirements.lock: {missing}. "
        "Regenerate the lock -- see the relock command in AGENTS.md. It must be "
        "cross-resolved for linux/3.11, not resolved on a Windows host."
    )


def test_the_lock_is_hash_pinned():
    """--require-hashes fails the build unless every entry carries hashes, so a
    lock generated without --generate-hashes breaks the image rather than
    weakening it. Catching it here beats catching it in a deploy."""
    text = LOCKFILE.read_text(encoding="utf-8")
    pinned = len(re.findall(r"^[A-Za-z0-9._-]+==", text, flags=re.MULTILINE))
    assert pinned, "requirements.lock pins nothing"
    assert "--hash=sha256:" in text, (
        "requirements.lock has no hashes, but the Dockerfile passes "
        "--require-hashes -- that build fails on every package."
    )


def test_the_lock_carries_the_linux_only_server_extras():
    """uvicorn[standard] pulls uvloop and httptools only on non-Windows.

    Resolving the lock on this Windows host omits both, and the resulting image
    loses them with no error -- uvicorn falls back to the stdlib event loop and
    the only symptom is being slower. Asserting on them is the cheapest proof
    that the lock was cross-resolved for the platform the image actually runs.
    """
    locked = _locked_packages()
    for name in ("uvloop", "httptools"):
        assert name in locked, (
            f"{name} is missing from requirements.lock, which means it was resolved "
            "for the wrong platform. Regenerate with --python-platform linux."
        )
