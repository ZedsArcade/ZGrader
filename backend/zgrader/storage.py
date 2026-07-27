"""On-disk artefacts belonging to a submission.

Lives outside the routers because both submission deletion and account
deletion need it, and a router importing another router is a cycle waiting
to happen.
"""

import shutil
from pathlib import Path

from zgrader.config import config


def purge_submission_files(code: str) -> None:
    """Remove a submission's scans and reports from disk.

    Deliberately does NOT pass ignore_errors=True: a deletion that quietly
    failed is indistinguishable from one that worked, and when the request is
    an erasure that matters. A permission problem should surface, not vanish.
    """
    for base in (config.scans_dir, config.reports_dir):
        folder = Path(base) / code
        if folder.exists():
            shutil.rmtree(folder)
