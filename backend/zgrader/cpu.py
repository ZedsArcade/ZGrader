"""How much of the machine one analysis is allowed to take.

Lives at package root rather than under `api/` because both entry points need
it: the API caps how many analyses run at once (see `api/capacity.py`), and the
worker runs one of its own. A cap on *how many* means little if each one still
fans out across every core.

Set through `cv2.setNumThreads` rather than an environment variable, which is
the part worth remembering. `OPENCV_NUM_THREADS` is not an OpenCV variable at
all -- the real one is `OPENCV_FOR_THREADS`, and it is honoured only by some
parallel backends. On a Windows build neither moved `getNumThreads()`, which
stayed at the CPU count for both. A knob that looks like a control and silently
does nothing is exactly what `test_compose_env_coverage.py` was written after.

NumPy's bundled OpenBLAS is a **separate** pool and ignores this entirely. It
reads `OMP_NUM_THREADS` / `OPENBLAS_NUM_THREADS` when it is imported, long
before any of this runs, so those are set in `docker-compose.yml` instead --
they cannot be applied from here at all.
"""

import logging

from zgrader.config import config

logger = logging.getLogger(__name__)


def pin_analysis_threads() -> int:
    """Hold OpenCV to `config.analysis_threads`, and report what took effect.

    Returns the count OpenCV reports afterwards, so a caller (or a test) can
    check the setting actually landed rather than trusting that it did.
    """
    import cv2

    requested = max(1, int(config.analysis_threads))
    cv2.setNumThreads(requested)
    effective = cv2.getNumThreads()
    if effective != requested:
        # Not fatal: an unbounded pipeline still produces correct results, it
        # just takes more of the box than intended. Worth a line in the log so
        # the reason a saturated machine is saturated is discoverable.
        logger.warning(
            "OpenCV thread pin did not take: requested %d, reports %d", requested, effective
        )
    else:
        logger.info("OpenCV limited to %d thread(s) per analysis", effective)
    return effective
