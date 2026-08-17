"""Bounding the CPU that API requests can consume.

`confirm-crop` runs the whole OpenCV pipeline synchronously inside the request,
and FastAPI runs sync endpoints in a 40-thread pool -- so before this, forty
concurrent submissions meant forty concurrent pipelines, and every other sync
endpoint queued behind them for a thread.

The tests below use **real threads** on purpose. A single-threaded test can
assert that the semaphore object has the right count, which proves nothing about
what happens when two requests actually overlap; the second caller has to be
blocked while the first is genuinely inside the guarded section.
"""

import threading
import time

import pytest
from fastapi import HTTPException

from zgrader.api import capacity


def _hold(user_id, code, entered, release, results, index):
    """Take a slot, signal that it is held, wait to be told to let go."""
    try:
        with capacity.analysis_slot(user_id, code):
            entered.set()
            release.wait(timeout=5)
        results[index] = "ok"
    except HTTPException as exc:
        results[index] = exc.status_code


# --- the global cap -------------------------------------------------------


def test_a_second_analysis_is_refused_while_the_cap_is_full():
    capacity._reset(cap=1)
    entered, release, results = threading.Event(), threading.Event(), {}

    holder = threading.Thread(target=_hold, args=("user-a", "SUB-1", entered, release, results, 0))
    holder.start()
    assert entered.wait(timeout=5), "first caller never entered the guarded section"

    # A different user, so this is the machine cap and not the per-user one.
    with pytest.raises(HTTPException) as caught:
        with capacity.analysis_slot("user-b", "SUB-2"):
            pass

    assert caught.value.status_code == 503
    assert caught.value.headers["Retry-After"]

    release.set()
    holder.join(timeout=5)
    assert results[0] == "ok"


def test_the_slot_is_returned_when_the_first_analysis_finishes():
    capacity._reset(cap=1)
    with capacity.analysis_slot("user-a", "SUB-1"):
        pass

    # Would raise if the slot had leaked.
    with capacity.analysis_slot("user-b", "SUB-2"):
        pass


def test_a_failing_analysis_does_not_leak_its_slot():
    """The path that matters: run_analysis raises PipelineError on a bad scan,
    and a leaked slot never comes back -- the cap would shrink by one for the
    life of the process, with nothing to point at."""
    capacity._reset(cap=1)

    with pytest.raises(RuntimeError):
        with capacity.analysis_slot("user-a", "SUB-1"):
            raise RuntimeError("pipeline blew up")

    with capacity.analysis_slot("user-b", "SUB-2"):
        pass


def test_capacity_is_taken_from_config():
    capacity._reset()
    from zgrader.config import config

    holders = []
    for i in range(config.max_concurrent_analyses):
        cm = capacity.analysis_slot(f"user-{i}", f"SUB-{i}")
        cm.__enter__()
        holders.append(cm)
    try:
        with pytest.raises(HTTPException) as caught:
            with capacity.analysis_slot("one-too-many", "SUB-X"):
                pass
        assert caught.value.status_code == 503
    finally:
        for cm in holders:
            cm.__exit__(None, None, None)


# --- the per-user cap -----------------------------------------------------


def test_one_user_cannot_run_two_analyses_at_once():
    capacity._reset(cap=4)  # plenty of machine capacity; the limit is per-user
    entered, release, results = threading.Event(), threading.Event(), {}

    holder = threading.Thread(target=_hold, args=("user-a", "SUB-1", entered, release, results, 0))
    holder.start()
    assert entered.wait(timeout=5)

    with pytest.raises(HTTPException) as caught:
        with capacity.analysis_slot("user-a", "SUB-2"):
            pass

    # 409, not 503: this is a state conflict for one account, not the machine
    # being busy. "You already have one running" is actionable; "server busy"
    # invites an immediate retry that fails the same way.
    assert caught.value.status_code == 409

    release.set()
    holder.join(timeout=5)
    assert results[0] == "ok"


def test_another_user_is_unaffected_by_someone_elses_in_flight_analysis():
    capacity._reset(cap=4)
    entered, release, results = threading.Event(), threading.Event(), {}

    holder = threading.Thread(target=_hold, args=("user-a", "SUB-1", entered, release, results, 0))
    holder.start()
    assert entered.wait(timeout=5)

    with capacity.analysis_slot("user-b", "SUB-2"):
        pass

    release.set()
    holder.join(timeout=5)


def test_a_refused_request_does_not_leave_the_user_marked_in_flight():
    """The 503 path adds the user to the in-flight set *before* trying for a
    slot. If it did not clean up, one unlucky refusal would lock that account
    out of analysis until the process restarted."""
    capacity._reset(cap=1)
    entered, release, results = threading.Event(), threading.Event(), {}

    holder = threading.Thread(target=_hold, args=("user-a", "SUB-1", entered, release, results, 0))
    holder.start()
    assert entered.wait(timeout=5)

    with pytest.raises(HTTPException) as caught:
        with capacity.analysis_slot("user-b", "SUB-2"):
            pass
    assert caught.value.status_code == 503

    release.set()
    holder.join(timeout=5)

    assert capacity.in_flight_count() == 0
    # user-b can try again now the machine is free.
    with capacity.analysis_slot("user-b", "SUB-2"):
        pass


def test_refusal_is_immediate_rather_than_a_wait():
    """Sized for a handful of analyses a day, so the cap should almost never
    bind -- and when it does, a caller left hanging is worse than one told to
    come back. A blocking acquire would also hold a threadpool thread for the
    length of somebody else's pipeline, which is the exact behaviour this
    guard exists to stop."""
    capacity._reset(cap=1)
    entered, release, results = threading.Event(), threading.Event(), {}

    holder = threading.Thread(target=_hold, args=("user-a", "SUB-1", entered, release, results, 0))
    holder.start()
    assert entered.wait(timeout=5)

    started = time.perf_counter()
    with pytest.raises(HTTPException):
        with capacity.analysis_slot("user-b", "SUB-2"):
            pass
    elapsed = time.perf_counter() - started

    assert elapsed < 0.25, f"refusal took {elapsed:.3f}s -- it should not wait at all"

    release.set()
    holder.join(timeout=5)


# --- the endpoint is actually wired to the guard --------------------------


def test_confirm_crop_returns_503_when_the_machine_is_full(db_session, sample_scan_paths):
    """Everything above tests the guard in isolation, which proves nothing
    about whether confirm-crop consults it. This holds the only slot from
    another thread and drives the real endpoint."""
    from fastapi.testclient import TestClient

    from zgrader.api.main import app

    from tests.conftest import register_and_verify

    client = TestClient(app)
    token = register_and_verify(client, "capacity@example.com")
    auth = {"Authorization": f"Bearer {token}"}

    code = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "Pikachu"},
        headers=auth,
    ).json()["submission_code"]
    with open(sample_scan_paths["pokemon_front"], "rb") as handle:
        client.post(
            f"/submissions/{code}/scans",
            files={"file": ("front.png", handle, "image/png")},
            data={"side": "front"},
            headers=auth,
        )
    points = client.get(
        f"/submissions/{code}/scans/front/suggest-crop", headers=auth
    ).json()["points"]

    capacity._reset(cap=1)
    entered, release, results = threading.Event(), threading.Event(), {}
    holder = threading.Thread(
        target=_hold, args=("someone-else", "SUB-OTHER", entered, release, results, 0)
    )
    holder.start()
    assert entered.wait(timeout=5)

    try:
        resp = client.post(
            f"/submissions/{code}/scans/front/confirm-crop",
            json={"points": points},
            headers=auth,
        )
    finally:
        release.set()
        holder.join(timeout=5)

    assert resp.status_code == 503, resp.text
    assert resp.headers.get("Retry-After")


# --- thread pinning -------------------------------------------------------


def test_opencv_threads_are_actually_pinned():
    """The setting is applied with cv2.setNumThreads rather than an environment
    variable, because `OPENCV_NUM_THREADS` is not an OpenCV variable and the
    real `OPENCV_FOR_THREADS` is honoured only by some parallel backends --
    neither moved getNumThreads() on a Windows build. This asserts the number
    took effect instead of trusting that it did."""
    import cv2

    from zgrader.config import config
    from zgrader.cpu import pin_analysis_threads

    previous = cv2.getNumThreads()
    try:
        effective = pin_analysis_threads()
        assert effective == config.analysis_threads
        assert cv2.getNumThreads() == config.analysis_threads
    finally:
        cv2.setNumThreads(previous)
