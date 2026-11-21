"""Stream worker output without pipe deadlocks; bound and reap external commands."""

from codecs import getincrementaldecoder
from contextlib import suppress
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


class CommandTimeout(RuntimeError):
    pass


def stop(process):
    """Terminate the entire session, including descendants of an exited leader."""
    if os.name == "posix":
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    elif process.poll() is None:
        process.kill()
    process.wait()


def run(args, *, env, output, timeout, input_text=None, secret=False,
        apt_status=None, heartbeat=None):
    """Return status, bounded output tail, full byte count. Callbacks run on worker.

    Independent read descriptors avoid seeking the child's output descriptor.
    A file also lets us enforce a deadline when a child emits no newline, or when
    a descendant holds stdout open after the group leader exits. Secret commands
    have neither captured output nor status events.
    """
    args = [os.fspath(arg) for arg in args]
    with tempfile.TemporaryDirectory(prefix="aphrodite-os-command-") as directory:
        path = Path(directory)
        with (path / "output").open("w+b") as capture, (path / "status").open("w+b") as status:
            passed = ()
            if apt_status and not secret:
                index = next(index for index, arg in enumerate(args) if Path(arg).name == "apt-get") + 1
                args[index:index] = ["-o", f"APT::Status-Fd={status.fileno()}",
                                     "-o", "Dpkg::Use-Pty=0", "-o", "Dpkg::Progress-Fancy=0"]
                passed = (status.fileno(),)
            kwargs = {"pass_fds": passed} if passed else {}
            with subprocess.Popen(args, stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL if secret else capture,
                                  stderr=subprocess.DEVNULL if secret else subprocess.STDOUT,
                                  env=env, start_new_session=True, **kwargs) as process:
                try:
                    if input_text is not None:
                        try:
                            process.stdin.write(input_text.encode("utf-8"))
                        except BrokenPipeError:
                            pass
                        finally:
                            process.stdin.close()
                    started = time.monotonic()
                    last_heartbeat = started
                    decoders = [getincrementaldecoder("utf-8")("replace") for _ in range(2)]
                    pending = ["", ""]
                    callbacks = [output, apt_status or (lambda _: None)]
                    with (path / "output").open("rb") as reader, (path / "status").open("rb") as statuses:
                        def drain(final=False):
                            for index, stream in enumerate((reader, statuses)):
                                # Bound each iteration so a noisy child cannot starve the deadline.
                                chunk = stream.read(65536)
                                text = decoders[index].decode(chunk, final=final)
                                pending[index] += text.replace("\r", "\n")
                                lines = pending[index].split("\n")
                                pending[index] = lines.pop()
                                for line in lines:
                                    if line.strip():
                                        callbacks[index](line[-4000:])
                                if final or len(pending[index]) > 16384:
                                    if pending[index].strip():
                                        callbacks[index](pending[index][-4000:])
                                    pending[index] = ""
                                return_more[index] = len(chunk) == 65536

                        return_more = [False, False]
                        while True:
                            drain()
                            now = time.monotonic()
                            if process.poll() is not None:
                                # Read all output after exit, without waiting for EOF from grandchildren.
                                drain()
                                while any(return_more):
                                    drain()
                                drain(final=True)
                                break
                            if now - started >= timeout:
                                stop(process)
                                drain()
                                while any(return_more):
                                    drain()
                                drain(final=True)
                                raise CommandTimeout(f"{args[0]} timed out after {timeout:g} seconds")
                            if heartbeat and now - last_heartbeat >= 5:
                                heartbeat(now - started)
                                last_heartbeat = now
                            time.sleep(.05)
                finally:
                    # Reap the leader and prevent child commands surviving a failed callback.
                    if process.poll() is None:
                        stop(process)
                length = os.fstat(capture.fileno()).st_size
                capture.seek(max(0, length - 200_001))
                text = capture.read().decode("utf-8", errors="replace")
                return process.returncode, text, length
