import asyncio
import contextlib
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# app/workers/supervisor.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class WorkerSupervisor:
    """Runs the ARQ worker as a child process of the API server.

    A subprocess rather than an in-process task: the worker drives Playwright/
    Chromium, which can crash or OOM independently of the API. Isolating it in
    its own process means that takes down job processing, not the API too.

    Uses `subprocess.Popen` (+ a thread for the blocking `.wait()`) instead of
    `asyncio.create_subprocess_exec`. uvicorn's `--reload` supervisor forces
    the served process onto a `SelectorEventLoop` on Windows, and Windows'
    `SelectorEventLoop` cannot create subprocesses at all — only
    `ProactorEventLoop` can, so the asyncio API raises `NotImplementedError`
    under `--reload`. `Popen` bypasses the event loop's subprocess machinery
    entirely, so it works under both loop types (confirmed: reproduced the
    NotImplementedError under `--reload` before this change, verified fixed
    after).
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._stopping = False

    async def start(self) -> None:
        self._stopping = False
        self._process = subprocess.Popen(
            [sys.executable, "-m", "arq", "app.workers.queue.WorkerSettings"], cwd=_BACKEND_ROOT
        )
        logger.info("Started ARQ worker subprocess (pid=%s)", self._process.pid)
        self._monitor_task = asyncio.create_task(self._monitor())

    async def _monitor(self) -> None:
        assert self._process is not None
        returncode = await asyncio.to_thread(self._process.wait)
        if not self._stopping:
            logger.error(
                "ARQ worker subprocess exited unexpectedly (code=%s) — queued discovery jobs "
                "will not be processed until the API is restarted",
                returncode,
            )

    async def stop(self) -> None:
        self._stopping = True
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None

        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(self._process.wait), timeout=10)
            except asyncio.TimeoutError:
                logger.warning("ARQ worker subprocess did not exit within 10s — killing it")
                self._process.kill()
                await asyncio.to_thread(self._process.wait)
        self._process = None
