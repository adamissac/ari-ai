"""In-sandbox bootstrap. Copied into each sandbox as `.sandbox/entry.py`.

STANDALONE: imports only the stdlib (plus pytest / the check harness when that
mode is selected). It runs *inside* the sandbox, so it is part of the untrusted
execution side; its job is to set up the process (sys.path, network guard) and
dispatch one of a fixed set of platform-defined modes:

    pytest <args...>            run the target's test suite
    check  <params.json>        run one reviewed check template (harness.py)
    netprobe <host> <port>      SB-03/SB-04 fixture: attempt a TCP connection

The network guard below is defence in depth for the local dev driver. It is NOT
the security boundary; Docker `--network none` / internal networks are.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import sys

WORKSPACE = os.getcwd()
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("SANDBOX_OUT", "/out")
NETWORK = os.environ.get("SANDBOX_NETWORK", "none")


def _install_network_guard() -> None:
    if NETWORK not in ("none", "target-inprocess"):
        return

    def _denied(*_a: object, **_k: object) -> None:
        raise PermissionError("SANDBOX_POLICY_VIOLATION: network disabled in this sandbox")

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self: socket.socket, address: object) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6):
            _denied()
        return real_connect(self, address)  # type: ignore[arg-type]

    def connect_ex(self: socket.socket, address: object) -> int:
        if self.family in (socket.AF_INET, socket.AF_INET6):
            _denied()
        return real_connect_ex(self, address)  # type: ignore[arg-type]

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.getaddrinfo = _denied  # type: ignore[assignment]
    socket.create_connection = _denied  # type: ignore[assignment]


def _emit_out() -> None:
    """Docker driver collects /out through stdout (no host mounts)."""
    if os.environ.get("SANDBOX_EMIT_OUT") != "1":
        return
    files: dict[str, str] = {}
    total = 0
    for name in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
        path = os.path.join(OUT, name)
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                data = fh.read()
            total += len(data)
            if total > 50 * 1024 * 1024:
                break
            files[name] = base64.b64encode(data).decode()
    sys.stdout.write("\n@@SANDBOX_OUT@@" + json.dumps(files) + "\n")
    sys.stdout.flush()


def main(argv: list[str]) -> int:
    if not argv:
        return 2
    mode, args = argv[0], argv[1:]
    sys.path[:0] = [WORKSPACE, HERE]
    sys.dont_write_bytecode = True
    _install_network_guard()
    code = 2
    try:
        if mode == "pytest":
            import pytest

            code = int(pytest.main(["-p", "no:cacheprovider", *args]))
        elif mode == "check":
            import harness  # type: ignore[import-not-found]

            code = harness.main(args[0], OUT)
        elif mode == "netprobe":
            host, port = args[0], int(args[1])
            result: dict[str, object] = {"host": host, "port": port}
            try:
                s = socket.create_connection((host, port), timeout=2)
                s.close()
                result["connected"] = True
            except Exception as exc:
                result["connected"] = False
                result["error"] = f"{type(exc).__name__}: {exc}"[:300]
            with open(os.path.join(OUT, "netprobe.json"), "w") as fh:
                json.dump(result, fh)
            code = 0
        else:
            sys.stderr.write(f"unknown sandbox mode {mode!r}\n")
            code = 2
    finally:
        _emit_out()
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
