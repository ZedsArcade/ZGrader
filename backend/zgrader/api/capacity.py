"""How much analysis the API will do at once, and what it says when it won't.

`confirm-crop` runs the whole OpenCV pipeline synchronously inside the request.
That is a deliberate design -- the customer gets their result on the same round
trip -- but it means request concurrency is CPU concurrency. FastAPI runs sync
endpoints in the anyio threadpool, which is **40 threads** by default, so
without a bound forty simultaneous submissions become forty simultaneous
pipelines. On a self-hosted box that does not just make analysis slow; it
starves everything else sharing the machine, and every other sync endpoint
queues behind the pipelines for its own turn in the pool.

Two limits, because they answer different questions:

* a **global cap** (`max_concurrent_analyses`) is about the machine, and a
  request that cannot get in is told the server is busy -- 503;
* a **per-user cap of one** is about a single customer, and a second request
  from someone who already has an analysis running is a state conflict -- 409.

Both acquire **without waiting**. At the load this is sized for the cap should
almost never bind, and a queue that never fills is only latency: a caller left
hanging with no response is worse than one told plainly to come back. Both are
released in a `finally`, so a PipelineError cannot leak a slot -- and a leaked
slot never comes back, because these counters live for the life of the process.

Deliberately *not* inside `pipeline.run_analysis`, even though AGENTS.md argues
the opposite for per-submission cleanup. That cleanup is a correctness guarantee
every caller needs identically, so it belongs where it cannot be forgotten. This
is a policy about who gets *refused*, and it differs by caller: the API rejects,
while the worker must queue, because a background poll has nowhere to report a
503 to. Putting a blocking semaphore in the pipeline would stall the worker
whenever the API was busy.

In-process, like `ratelimit.py` and for the same reason: one uvicorn worker on
one box. If this ever runs multi-worker the cap multiplies by the worker count
and this needs replacing.
"""

import threading
from contextlib import contextmanager

from fastapi import HTTPException, status

from zgrader.config import config

#: Suggested wait, in seconds, sent with a 503. Long enough that a client
#: retrying immediately does not simply collide again, short enough that a
#: customer is not left staring at a spinner.
RETRY_AFTER_SECONDS = 20

_slots = threading.BoundedSemaphore(config.max_concurrent_analyses)
_in_flight: set[str] = set()
_lock = threading.Lock()


def _reset(cap: int | None = None) -> None:
    """Test helper. The state is process-global, so it has to be clearable --
    and resizable, since testing a cap of N is far easier at N=1."""
    global _slots
    _slots = threading.BoundedSemaphore(cap if cap is not None else config.max_concurrent_analyses)
    with _lock:
        _in_flight.clear()


def in_flight_count() -> int:
    with _lock:
        return len(_in_flight)


@contextmanager
def analysis_slot(user_id, submission_code: str):
    """Hold a slot for one analysis, or refuse the request.

    Raises before doing any work rather than blocking, so a refused caller
    releases its threadpool thread immediately instead of occupying one for the
    length of somebody else's pipeline -- which is the thing that made a burst
    degrade unrelated endpoints in the first place.
    """
    key = str(user_id)

    # The per-user check comes first. It is the cheaper answer and the more
    # useful one: telling somebody "you already have one running" is actionable,
    # where "the server is busy" invites an immediate retry that will fail the
    # same way.
    with _lock:
        if key in _in_flight:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "An analysis is already running for your account. Wait for it to "
                "finish before starting another.",
            )
        _in_flight.add(key)

    try:
        if not _slots.acquire(blocking=False):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "The analysis queue is full right now. Please try again shortly.",
                headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
            )
        try:
            yield
        finally:
            _slots.release()
    finally:
        # Runs whether the slot was acquired or not, so the 503 path cannot
        # leave the caller marked as in-flight and lock them out of retrying.
        with _lock:
            _in_flight.discard(key)
