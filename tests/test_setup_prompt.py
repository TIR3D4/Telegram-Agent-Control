"""Exercise the real controlling terminal, including a piped/redirected stdin."""

import errno
import os
from pathlib import Path
import pty
import select
import signal
import sys
import time


def test_setup_prompt_works_with_redirected_stdin_and_hidden_password():
    script = Path(__file__).resolve().parents[1] / "scripts/setup_access.py"
    code = (
        "import os,runpy,getpass; "
        "fd=os.open(os.devnull,os.O_RDONLY); os.dup2(fd,0); os.close(fd); "
        f"setup=runpy.run_path({str(script)!r}); "
        "assert setup['prompt']('Username: ') == 'test-owner'; "
        "assert getpass.getpass('Password: ') == 'fixture-password-hidden'; "
        "print('PROMPT_OK')"
    )
    pid, terminal = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-c", code])
    output = b""
    sent_user = sent_password = False
    exited = False
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if select.select([terminal], [], [], 0.2)[0]:
                try:
                    part = os.read(terminal, 4096)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not part:
                    break
                output += part
                if b"Username: " in output and not sent_user:
                    os.write(terminal, b"test-owner\n")
                    sent_user = True
                if b"Password: " in output and not sent_password:
                    os.write(terminal, b"fixture-password-hidden\n")
                    sent_password = True
            ended, status = os.waitpid(pid, os.WNOHANG)
            if ended:
                exited = True
                assert os.waitstatus_to_exitcode(status) == 0, output.decode(errors="replace")
                break
        assert b"PROMPT_OK" in output, output.decode(errors="replace")
        assert b"fixture-password-hidden" not in output
    finally:
        os.close(terminal)
        if not exited:
            ended, _ = os.waitpid(pid, os.WNOHANG)
            if not ended:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
