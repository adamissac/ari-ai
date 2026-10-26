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
import hashlib
import json
import os
import socket
import sys
import types

WORKSPACE = os.getcwd()
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("SANDBOX_OUT", "/out")
NETWORK = os.environ.get("SANDBOX_NETWORK", "none")


def _code_tuple(code: types.CodeType) -> tuple[object, ...]:
    constants = tuple(
        _code_tuple(value) if isinstance(value, types.CodeType) else repr(value) for value in code.co_consts
    )
    return (
        code.co_code,
        code.co_names,
        code.co_varnames,
        code.co_freevars,
        code.co_cellvars,
        code.co_argcount,
        code.co_kwonlyargcount,
        getattr(code, "co_posonlyargcount", 0),
        code.co_flags,
        constants,
    )


def _code_sha256(function: object) -> str:
    code = getattr(function, "__code__", None)
    value = (
        repr(_code_tuple(code))
        if isinstance(code, types.CodeType)
        else (f"{type(function).__module__}.{type(function).__qualname__}")
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _relative_code_file(function: object) -> str:
    code = getattr(function, "__code__", None)
    filename = getattr(code, "co_filename", None)
    if not isinstance(filename, str):
        return "<external>"
    cwd = os.path.abspath(os.getcwd())
    path = os.path.abspath(filename)
    try:
        if os.path.commonpath((cwd, path)) == cwd:
            return os.path.relpath(path, cwd)
    except ValueError:
        pass
    return "<external>"


def _build_pytest_audit_plugin(pytest: object) -> object:
    class PytestAuditPlugin:
        def __init__(self) -> None:
            self.phases: dict[str, list[dict[str, object]]] = {}
            self.nodeids: list[str] = []
            self.outcomes: dict[str, str] = {}
            self.complete = False
            self.session_finished = False
            self.written = False

        def _snapshot(self, config: object) -> list[dict[str, object]]:
            pluginmanager = config.pluginmanager
            relay = pluginmanager.hook
            entries: list[dict[str, object]] = []
            for name in dir(relay):
                caller = getattr(relay, name, None)
                get_hookimpls = getattr(caller, "get_hookimpls", None)
                if not callable(get_hookimpls):
                    continue
                for hookimpl in get_hookimpls():
                    if getattr(hookimpl, "plugin", None) is self:
                        continue
                    function = getattr(hookimpl, "function", hookimpl)
                    flags = sorted(
                        flag
                        for flag in ("tryfirst", "trylast", "wrapper", "hookwrapper")
                        if bool(getattr(hookimpl, flag, False))
                    )
                    entries.append(
                        {
                            "hook": name,
                            "module": getattr(function, "__module__", type(function).__module__),
                            "qualname": getattr(function, "__qualname__", type(function).__qualname__),
                            "file": _relative_code_file(function),
                            "flags": flags,
                            "code_sha256": _code_sha256(function),
                        }
                    )
            return sorted(
                entries,
                key=lambda entry: (
                    str(entry["hook"]),
                    str(entry["module"]),
                    str(entry["qualname"]),
                    str(entry["file"]),
                    tuple(entry["flags"]),
                    str(entry["code_sha256"]),
                ),
            )

        def _write(self) -> None:
            try:
                os.makedirs(OUT, exist_ok=True)
                with open(os.path.join(OUT, "pytest_audit.json"), "w", encoding="utf-8") as stream:
                    json.dump(
                        {
                            "version": 1,
                            "complete": self.complete,
                            "phases": self.phases,
                            "nodeids": self.nodeids,
                            "outcomes": self.outcomes,
                        },
                        stream,
                        sort_keys=True,
                    )
                self.written = True
            except Exception:
                pass

        @pytest.hookimpl(trylast=True)
        def pytest_collection_finish(self, session: object) -> None:
            self.phases["collection"] = self._snapshot(session.config)
            self.nodeids = [str(item.nodeid) for item in session.items]

        @pytest.hookimpl(trylast=True)
        def pytest_runtest_logreport(self, report: object) -> None:
            nodeid = str(report.nodeid)
            when = str(report.when)
            has_xfail = hasattr(report, "wasxfail")
            if has_xfail and when == "call":
                self.outcomes[nodeid] = "xfailed" if bool(report.skipped) else "xpassed"
            elif when == "call":
                if bool(report.passed):
                    self.outcomes[nodeid] = "passed"
                elif bool(report.failed):
                    self.outcomes[nodeid] = "failed"
                elif bool(report.skipped):
                    self.outcomes[nodeid] = "skipped"
            elif when == "setup" and bool(report.skipped):
                self.outcomes[nodeid] = "skipped"
            elif when in ("setup", "teardown") and bool(report.failed):
                self.outcomes[nodeid] = "error"

        @pytest.hookimpl(trylast=True)
        def pytest_sessionfinish(self, session: object, exitstatus: int) -> None:
            self.phases["final"] = self._snapshot(session.config)
            self.complete = True
            self.session_finished = True
            self._write()

        @pytest.hookimpl(trylast=True)
        def pytest_unconfigure(self, config: object) -> None:
            if not self.written:
                self.complete = self.session_finished
                self._write()

    return PytestAuditPlugin()


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
    audit = None
    if mode == "pytest":
        import pluggy
        import pytest

        _ = pluggy.PluginManager
        audit = _build_pytest_audit_plugin(pytest)

    sys.path[:0] = [WORKSPACE, HERE]
    sys.dont_write_bytecode = True
    _install_network_guard()
    code = 2
    try:
        if mode == "pytest":
            code = int(pytest.main(["-p", "no:cacheprovider", *args], plugins=[audit]))
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
