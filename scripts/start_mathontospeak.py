from __future__ import annotations

import argparse
import os
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "demo" / "frontend"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
FUSEKI_SCRIPT = ROOT / "scripts" / "start_fuseki_mathkg.ps1"


@dataclass(frozen=True)
class Service:
    name: str
    host: str
    port: int
    command: tuple[str, ...]
    cwd: Path
    startup_timeout: float


def port_is_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def service_definitions(*, include_fuseki: bool = True) -> list[Service]:
    npm = shutil.which("npm.cmd") or "npm.cmd"
    powershell = shutil.which("powershell.exe") or "powershell.exe"
    services: list[Service] = []
    if include_fuseki:
        services.append(
            Service(
                name="ONTOLOGY",
                host="127.0.0.1",
                port=3030,
                command=(
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(FUSEKI_SCRIPT),
                ),
                cwd=ROOT,
                startup_timeout=30,
            )
        )
    services.extend(
        [
            Service(
                name="API",
                host="127.0.0.1",
                port=8000,
                command=(
                    str(VENV_PYTHON),
                    "-m",
                    "uvicorn",
                    "api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--log-level",
                    "info",
                ),
                cwd=ROOT,
                startup_timeout=60,
            ),
            Service(
                name="WEB",
                host="127.0.0.1",
                port=5173,
                command=(npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"),
                cwd=FRONTEND,
                startup_timeout=30,
            ),
        ]
    )
    return services


def validate_installation(services: list[Service]) -> list[str]:
    problems: list[str] = []
    if not VENV_PYTHON.is_file():
        problems.append(f"Python environment not found: {VENV_PYTHON}")
    if not FRONTEND.joinpath("package.json").is_file():
        problems.append(f"Frontend package not found: {FRONTEND / 'package.json'}")
    if any(service.name == "ONTOLOGY" for service in services) and not FUSEKI_SCRIPT.is_file():
        problems.append(f"Fuseki launcher not found: {FUSEKI_SCRIPT}")
    if shutil.which("npm.cmd") is None:
        problems.append("npm.cmd was not found on PATH. Install Node.js or reopen VS Code after installation.")
    return problems


def stream_output(
    service: Service,
    process: subprocess.Popen[str],
    messages: queue.Queue[tuple[str, str]],
) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        text = line.rstrip()
        if text:
            messages.put((service.name, text))


def start_service(
    service: Service,
    messages: queue.Queue[tuple[str, str]],
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        list(service.command),
        cwd=service.cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
    )
    threading.Thread(
        target=stream_output,
        args=(service, process, messages),
        daemon=True,
    ).start()
    return process


def wait_until_ready(service: Service, process: subprocess.Popen[str]) -> bool:
    deadline = time.monotonic() + service.startup_timeout
    while time.monotonic() < deadline:
        if port_is_open(service.host, service.port):
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.wait(timeout=4)
            return
        except (OSError, subprocess.TimeoutExpired):
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )
            return
    process.terminate()
    try:
        process.wait(timeout=4)
    except subprocess.TimeoutExpired:
        process.kill()


def print_status(services: list[Service]) -> bool:
    print("MathOntoSpeak service status")
    all_ready = True
    for service in services:
        ready = port_is_open(service.host, service.port)
        all_ready = all_ready and ready
        state = "ready" if ready else "stopped"
        print(f"  [{service.name:<8}] {state:<7} http://{service.host}:{service.port}")
    return all_ready


def run(args: argparse.Namespace) -> int:
    services = service_definitions(include_fuseki=not args.skip_fuseki)
    problems = validate_installation(services)
    if problems:
        print("MathOntoSpeak could not start:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if args.check:
        return 0 if print_status(services) else 1

    print("MathOntoSpeak unified launcher")
    print("All services are supervised in this terminal. Press Ctrl+C to stop MathOntoSpeak.\n")
    messages: queue.Queue[tuple[str, str]] = queue.Queue()
    managed: dict[str, subprocess.Popen[str] | None] = {}
    owned: dict[str, subprocess.Popen[str]] = {}

    try:
        for service in services:
            if port_is_open(service.host, service.port):
                print(f"[{service.name:<8}] already running on port {service.port}")
                managed[service.name] = None
                continue
            print(f"[{service.name:<8}] starting on port {service.port}...")
            process = start_service(service, messages)
            managed[service.name] = process
            owned[service.name] = process
            if not wait_until_ready(service, process):
                while not messages.empty():
                    source, line = messages.get_nowait()
                    print(f"[{source:<8}] {line}")
                print(f"[{service.name:<8}] failed to become ready.", file=sys.stderr)
                return 1
            print(f"[{service.name:<8}] ready at http://{service.host}:{service.port}")

        print("\nMathOntoSpeak is ready: http://127.0.0.1:5173/")
        print("API documentation:      http://127.0.0.1:8000/docs")
        if not args.no_browser:
            webbrowser.open("http://127.0.0.1:5173/")

        if not owned:
            print("All services were already running; their ports are now supervised by this launcher.")

        while True:
            try:
                source, line = messages.get(timeout=0.25)
                print(f"[{source:<8}] {line}")
            except queue.Empty:
                pass
            for service in services:
                if port_is_open(service.host, service.port):
                    continue
                previous = managed.get(service.name)
                if previous is not None and previous.poll() is None:
                    stop_process_tree(previous)
                print(f"[{service.name:<8}] unavailable; restarting on port {service.port}...", file=sys.stderr)
                replacement = start_service(service, messages)
                managed[service.name] = replacement
                owned[service.name] = replacement
                if wait_until_ready(service, replacement):
                    print(f"[{service.name:<8}] recovered at http://{service.host}:{service.port}")
                else:
                    while not messages.empty():
                        source, line = messages.get_nowait()
                        print(f"[{source:<8}] {line}")
                    print(
                        f"[{service.name:<8}] restart failed; the supervisor will retry.",
                        file=sys.stderr,
                    )
            if getattr(args, "monitor_once", False):
                return 0
    except KeyboardInterrupt:
        print("\nStopping MathOntoSpeak...")
        return 0
    finally:
        for service in reversed(services):
            process = owned.get(service.name)
            if process is None:
                continue
            if process.poll() is None:
                print(f"[{service.name:<8}] stopping")
                stop_process_tree(process)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the complete local MathOntoSpeak stack in one terminal.")
    parser.add_argument("--check", action="store_true", help="Show service status without starting anything.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the app automatically.")
    parser.add_argument("--skip-fuseki", action="store_true", help="Run without starting the local ontology server.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
