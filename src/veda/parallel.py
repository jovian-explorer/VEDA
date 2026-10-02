"""Parallel work: worker processes for CPU-heavy batches, threads for downloads.

The number of worker processes is the ``cpu_workers`` setting (Settings >
Performance); with 1, everything runs in the main process.  Workers are started
once and reused, so their start-up cost (importing NumPy and SciPy) is paid once
per session, not per task.  Functions sent to workers must be importable
module-level functions and their arguments and results picklable.

Downloads are network-bound, so they use threads (``download_workers``) instead.
"""
from __future__ import annotations

import atexit
import os
import threading
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, Iterator, List, Optional, Sequence, Tuple

_pool: Optional[ProcessPoolExecutor] = None
_pool_size = 0
_lock = threading.Lock()


def cpu_workers() -> int:
    from .config import SETTINGS
    return max(1, int(getattr(SETTINGS, "cpu_workers", 1) or 1))


def download_workers() -> int:
    from .config import SETTINGS
    return max(1, int(getattr(SETTINGS, "download_workers", 4) or 4))


def _worker_init(home: Optional[str]) -> None:
    # Same data folder as the main process (the catalogue, cache and settings).
    if home:
        os.environ["VEDA_HOME"] = home
    # Exit when VEDA does.  A worker only notices a normal shutdown; if the app is
    # killed or crashes, the workers would otherwise stay running, holding memory.
    threading.Thread(target=_exit_with_parent, daemon=True).start()
    # Import the heavy modules now, in parallel across the workers, instead of on each
    # worker's first task (SciPy's signal module alone takes seconds).
    try:
        import importlib
        for mod in ("veda.archives.profiles", "veda.analysis.wave_and_stability", "veda.readers.product"):
            importlib.import_module(mod)
    except Exception:  # noqa: BLE001 - only an optimisation
        pass


def _exit_with_parent() -> None:
    import multiprocessing
    parent = multiprocessing.parent_process()
    if parent is not None:
        parent.join()          # returns when the parent process has ended
        os._exit(0)


def warm_up() -> None:
    """Start the worker processes now (called at app start-up, in the background)."""
    pool = process_pool()
    if pool is not None:
        list(pool.map(_noop, range(cpu_workers())))


def _noop(_x: int) -> None:
    return None


def process_pool() -> Optional[ProcessPoolExecutor]:
    """The shared worker pool, resized when the setting changed; None for 1 worker."""
    global _pool, _pool_size
    n = cpu_workers()
    with _lock:
        if n <= 1:
            if _pool is not None:
                _pool.shutdown(wait=False, cancel_futures=True)
                _pool, _pool_size = None, 0
            return None
        if _pool is None or _pool_size != n:
            if _pool is not None:
                _pool.shutdown(wait=False, cancel_futures=True)
            import multiprocessing
            from .config import DATA_ROOT
            _pool = ProcessPoolExecutor(max_workers=n, mp_context=multiprocessing.get_context("spawn"),
                                        initializer=_worker_init, initargs=(str(DATA_ROOT),))
            _pool_size = n
        return _pool


def shutdown() -> None:
    global _pool
    with _lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
            _pool = None


atexit.register(shutdown)


def _run_chunk(fn: Callable[..., Any], arg_tuples: List[Tuple]) -> List[Any]:
    out = []
    for a in arg_tuples:
        try:
            out.append(fn(*a))
        except Exception as exc:  # noqa: BLE001 - returned in place of the result
            out.append(exc)
    return out


def cpu_map(fn: Callable[..., Any], arg_tuples: Sequence[Tuple], min_parallel: int = 3) -> List[Any]:
    """[fn(*args) for args in arg_tuples] in worker processes, results in input order.

    Each result is either the return value or the exception the call raised (as
    the value), so one bad item never loses the others.  Small batches run in the
    main process, where starting workers would cost more than it saves.
    """
    items = list(arg_tuples)
    pool = process_pool() if len(items) >= min_parallel else None
    if pool is None:
        out = []
        for a in items:
            try:
                out.append(fn(*a))
            except Exception as exc:  # noqa: BLE001 - returned to the caller
                out.append(exc)
        return out
    from concurrent.futures.process import BrokenProcessPool
    out: List[Any] = [None] * len(items)
    pending = set(range(len(items)))
    # Chunks of several items per task (about four per worker): handing a task to a
    # worker costs ~10 ms on Windows, as much as reading a small profile.
    n_chunks = min(len(items), cpu_workers() * 4)
    chunks = [list(range(k, len(items), n_chunks)) for k in range(n_chunks)]
    try:
        futures = {pool.submit(_run_chunk, fn, [items[i] for i in idx]): idx for idx in chunks}
        for fut in as_completed(futures):
            idx = futures[fut]
            for i, res in zip(idx, fut.result()):
                out[i] = res
                pending.discard(i)
    except BrokenProcessPool:
        # A worker died (killed, out of memory, or no importable main module):
        # finish in this process and start a fresh pool next time.
        shutdown()
        for i in sorted(pending):
            try:
                out[i] = fn(*items[i])
            except Exception as exc:  # noqa: BLE001
                out[i] = exc
    return out


def thread_map(fn: Callable[..., Any], arg_tuples: Iterable[Tuple], workers: Optional[int] = None,
               on_done: Optional[Callable[[int, Any], None]] = None) -> List[Any]:
    """Like cpu_map, with threads (downloads, archive listings); ``on_done(i, result)``
    is called as each finishes (progress reporting)."""
    items = list(arg_tuples)
    n = min(len(items), workers or download_workers()) or 1
    out: List[Any] = [None] * len(items)

    def call(i, a):
        try:
            return i, fn(*a)
        except Exception as exc:  # noqa: BLE001
            return i, exc
    if n == 1:
        for i, a in enumerate(items):
            out[i] = call(i, a)[1]
            if on_done:
                on_done(i, out[i])
        return out
    with ThreadPoolExecutor(max_workers=n) as ex:
        for fut in as_completed([ex.submit(call, i, a) for i, a in enumerate(items)]):
            i, res = fut.result()
            out[i] = res
            if on_done:
                on_done(i, res)
    return out
