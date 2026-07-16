import asyncio
import threading
from unittest.mock import Mock, patch

from app.workers.supervisor import WorkerSupervisor


def _mock_process(pid: int = 4242) -> Mock:
    """A fake `subprocess.Popen` whose blocking wait() only resolves once
    "killed" — mirrors real subprocess semantics. `wait()` runs on a real
    thread (via `asyncio.to_thread` in the supervisor), so a real
    `threading.Event` is what actually models that correctly here.
    """
    process = Mock()
    process.pid = pid
    process.returncode = None
    exited = threading.Event()

    def _wait():
        exited.wait()
        return process.returncode

    def _simulate_exit(code: int) -> None:
        process.returncode = code
        exited.set()

    process.wait = Mock(side_effect=_wait)
    process.poll = Mock(side_effect=lambda: process.returncode)
    process.terminate = Mock(side_effect=lambda: _simulate_exit(0))
    process.kill = Mock(side_effect=lambda: _simulate_exit(-9))
    process.simulate_exit = _simulate_exit
    return process


async def test_start_spawns_arq_worker_subprocess():
    process = _mock_process()
    with patch("app.workers.supervisor.subprocess.Popen", return_value=process) as spawn:
        supervisor = WorkerSupervisor()
        await supervisor.start()
        try:
            spawn.assert_called_once()
            args = spawn.call_args.args[0]
            assert args[-3:] == ["-m", "arq", "app.workers.queue.WorkerSettings"]
        finally:
            await supervisor.stop()


async def test_stop_terminates_process_gracefully():
    process = _mock_process()

    with patch("app.workers.supervisor.subprocess.Popen", return_value=process):
        supervisor = WorkerSupervisor()
        await supervisor.start()
        await supervisor.stop()

    process.terminate.assert_called_once()
    process.kill.assert_not_called()


async def test_stop_kills_process_if_it_does_not_exit_in_time():
    process = _mock_process()
    process.terminate = Mock()  # simulate a process that ignores SIGTERM

    with patch("app.workers.supervisor.subprocess.Popen", return_value=process):
        supervisor = WorkerSupervisor()
        await supervisor.start()
        with patch("app.workers.supervisor.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            await supervisor.stop()

    process.terminate.assert_called_once()
    process.kill.assert_called_once()


async def test_unexpected_exit_is_logged_when_not_stopping(caplog):
    process = _mock_process()

    with patch("app.workers.supervisor.subprocess.Popen", return_value=process):
        supervisor = WorkerSupervisor()
        with caplog.at_level("ERROR"):
            await supervisor.start()
            process.simulate_exit(1)
            await supervisor._monitor_task

    assert "exited unexpectedly" in caplog.text
