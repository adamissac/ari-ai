"""In-sandbox bootstrap. Copied into each sandbox as `.sandbox/entry.py`.

STANDALONE: imports only the stdlib (plus pytest / the check harness when that
mode is selected). It runs *inside* the sandbox, so it is part of the untrusted
execution side; its job is to set up the process (sys.path, network guard) and
dispatch one of a fixed set of platform-defined modes:

    pytest <args...>            run the target's test suite
    check  <params.json>        run one reviewed check template (harness.py)
    netprobe <host> <port>      SB-03/SB-04 fixture: attempt a TCP connection
    nodetest <runner> <args...> run the target's vitest/jest suite (ADR-0023)

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


def _canonical_const(value: object) -> object:
    if isinstance(value, types.CodeType):
        return _code_tuple(value)
    if isinstance(value, (frozenset, set)):
        return ("frozenset", tuple(sorted(repr(_canonical_const(item)) for item in value)))
    if isinstance(value, tuple):
        return ("tuple", tuple(_canonical_const(item) for item in value))
    return repr(value)


def _code_tuple(code: types.CodeType) -> tuple[object, ...]:
    constants = tuple(_canonical_const(value) for value in code.co_consts)
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
    if NETWORK not in ("none", "target-inprocess", "loopback"):
        return
    # loopback: the local driver's Node target and emulators listen on 127.0.0.1 only.
    loopback = NETWORK == "loopback"

    def _denied(*_a: object, **_k: object) -> None:
        raise PermissionError("SANDBOX_POLICY_VIOLATION: network disabled in this sandbox")

    def _local(address: object) -> bool:
        return loopback and isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1")

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo
    real_create_connection = socket.create_connection

    def connect(self: socket.socket, address: object) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _local(address):
            _denied()
        return real_connect(self, address)  # type: ignore[arg-type]

    def connect_ex(self: socket.socket, address: object) -> int:
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _local(address):
            _denied()
        return real_connect_ex(self, address)  # type: ignore[arg-type]

    def getaddrinfo(host: object, *a: object, **k: object) -> object:
        if not (loopback and host in ("127.0.0.1", "::1", "localhost")):
            _denied()
        return real_getaddrinfo(host, *a, **k)  # type: ignore[arg-type]

    def create_connection(address: object, *a: object, **k: object) -> object:
        if not _local(address):
            _denied()
        return real_create_connection(address, *a, **k)  # type: ignore[arg-type]

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
    socket.create_connection = create_connection  # type: ignore[assignment]


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


NODE_RUNNERS = {
    "vitest": ("node_modules/vitest/vitest.mjs", ["--reporter=json", "--outputFile={out}"]),
    "jest": ("node_modules/jest/bin/jest.js", ["--json", "--outputFile={out}"]),
}


def _node_test(runner: str, args: list[str]) -> int:
    """Run the target's own vitest/jest (JSON reporter) and report in pytest's shape: the
    summary line, `FAILED <id>` lines, and a test-id audit (hook audit is pytest-only)."""
    import subprocess

    if runner not in NODE_RUNNERS:
        print(f"1 error: unknown node test runner {runner!r}")
        return 2
    script, extra = NODE_RUNNERS[runner]
    report = os.path.join(OUT, "node_tests.json")
    cmd = ["node", os.path.join(WORKSPACE, script), *args, *(e.format(out=report) for e in extra)]
    proc = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True)
    sys.stderr.write(proc.stderr[-20000:])
    try:
        with open(report) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        print(proc.stdout[-5000:])
        print("1 error: the node test runner produced no JSON report")
        return 2
    outcomes: dict[str, str] = {}
    for suite in data.get("testResults", []):
        rel = os.path.relpath(str(suite.get("name", "")), WORKSPACE)
        for case in suite.get("assertionResults", []):
            title = str(case.get("fullName") or case.get("title") or "")
            nodeid = rel + "::" + "_".join(title.split())
            status = str(case.get("status"))
            outcomes[nodeid] = {"passed": "passed", "failed": "failed"}.get(status, "skipped")
        if suite.get("status") == "failed" and not suite.get("assertionResults"):
            outcomes[rel + "::<collection>"] = "error"
    for nodeid, outcome in sorted(outcomes.items()):
        if outcome == "failed":
            print(f"FAILED {nodeid}")
    counts = {
        k: sum(1 for o in outcomes.values() if o == k) for k in ("passed", "failed", "skipped", "error")
    }
    print(", ".join(f"{n} {k}" for k, n in counts.items() if n) or "no tests ran")
    with open(os.path.join(OUT, "pytest_audit.json"), "w") as fh:
        json.dump(
            {
                "version": 1,
                "complete": True,
                "runner": runner,
                "phases": {"collection": [], "final": []},
                "nodeids": sorted(outcomes),
                "outcomes": outcomes,
            },
            fh,
        )
    return 0 if outcomes and not counts["failed"] and not counts["error"] else 1


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
        elif mode == "nodetest":
            code = _node_test(args[0], args[1:])
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
