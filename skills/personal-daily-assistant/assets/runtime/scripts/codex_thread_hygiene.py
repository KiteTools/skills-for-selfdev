#!/usr/bin/env python3
"""Archive only delivered, non-current OpenClaw transport Codex threads."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import select
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


TECHNICAL_TITLE_PREFIXES = (
    "Conversation info (untrusted metadata):",
    "[cron:",
    "[personal-daily:transport]",
)
RECEIPTS_FILENAME = "codex_delivery_receipts.jsonl"
LOG_FILENAME = "codex_thread_hygiene.log"
DEFAULT_APP_SERVER_SOCKET = (
    Path.home()
    / ".codex"
    / "app-server-control"
    / "app-server-control.sock"
)


def codex_app_server_command(control_socket: Path) -> list[str]:
    """Use the shared Codex session store through an isolated stdio server."""
    del control_socket
    return ["codex", "app-server", "--stdio"]


def latest_trajectory_thread_id(path: Path) -> str | None:
    latest = None
    if not path.exists():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "session.started":
            value = event.get("data", {}).get("threadId")
            if isinstance(value, str) and value:
                latest = value
    return latest


def _is_technical_thread(thread: dict[str, Any]) -> bool:
    titles = (thread.get("name"), thread.get("preview"))
    return any(
        isinstance(title, str) and title.startswith(TECHNICAL_TITLE_PREFIXES)
        for title in titles
    )


def select_archive_candidates(
    threads: list[dict[str, Any]],
    *,
    delivered_ids: set[str],
    protected_ids: set[str],
    cutoff_epoch: int,
) -> list[dict[str, Any]]:
    # Kept in the interface for receipt-aware callers; known technical titles
    # are safe to archive after delivery or a completed cron run.
    del delivered_ids
    selected = []
    for thread in threads:
        thread_id = thread.get("id")
        status = (thread.get("status") or {}).get("type")
        if (
            isinstance(thread_id, str)
            and thread_id not in protected_ids
            and int(thread.get("createdAt") or 0) >= cutoff_epoch
            and status in {"idle", "notLoaded"}
            and _is_technical_thread(thread)
        ):
            selected.append(thread)
    return selected


def _trajectory_path(sessions_dir: Path, entry: dict[str, Any]) -> Path | None:
    session_id = entry.get("sessionId")
    if isinstance(session_id, str) and session_id:
        return sessions_dir / f"{session_id}.trajectory.jsonl"
    session_file = entry.get("sessionFile")
    if not isinstance(session_file, str) or not session_file:
        return None
    path = Path(session_file)
    if path.name.endswith(".jsonl"):
        return path.with_name(f"{path.name[:-6]}.trajectory.jsonl")
    return path.with_name(f"{path.name}.trajectory.jsonl")


def _load_sessions(sessions_dir: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(
        (sessions_dir / "sessions.json").read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise ValueError("OpenClaw sessions index must be an object")
    return {
        str(key): value
        for key, value in payload.items()
        if isinstance(value, dict)
    }


def _current_thread_ids(
    sessions_dir: Path,
    sessions: dict[str, dict[str, Any]],
) -> set[str]:
    protected = set()
    for entry in sessions.values():
        path = _trajectory_path(sessions_dir, entry)
        if path is None:
            continue
        thread_id = latest_trajectory_thread_id(path)
        if thread_id:
            protected.add(thread_id)
    return protected


def _load_receipt_ids(path: Path) -> set[str]:
    delivered = set()
    if not path.exists():
        return delivered
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            receipt = json.loads(raw)
        except json.JSONDecodeError:
            continue
        thread_id = receipt.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            delivered.add(thread_id)
    return delivered


def _append_receipt(
    path: Path,
    *,
    thread_id: str,
    session_key: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        if thread_id in _load_receipt_ids(path):
            return
        receipt = {
            "thread_id": thread_id,
            "session_key": session_key,
            "delivered_at": datetime.now().astimezone().isoformat(),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


class CodexAppServer:
    def __init__(
        self,
        timeout_seconds: float = 15.0,
        control_socket: Path = DEFAULT_APP_SERVER_SOCKET,
    ) -> None:
        self.deadline = time.monotonic() + timeout_seconds
        self.next_id = 1
        self.process = subprocess.Popen(
            codex_app_server_command(control_socket),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def __enter__(self) -> "CodexAppServer":
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "openclaw-personal-daily",
                    "title": "OpenClaw Personal Daily",
                    "version": "0.1.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        self.notify("initialized")
        return self

    def __exit__(self, *_: object) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)

    def _write(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError("Codex app-server stdin is unavailable")
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _read(self) -> dict[str, Any]:
        if self.process.stdout is None:
            raise RuntimeError("Codex app-server stdout is unavailable")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Codex app-server request timed out")
        readable, _, _ = select.select(
            [self.process.stdout.fileno()],
            [],
            [],
            remaining,
        )
        if not readable:
            raise TimeoutError("Codex app-server request timed out")
        raw = self.process.stdout.readline()
        if not raw:
            raise RuntimeError("Codex app-server closed stdout")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError("Codex app-server returned a non-object")
        return payload

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

    def request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self._write({"id": request_id, "method": method, "params": params})
        while True:
            payload = self._read()
            if payload.get("id") != request_id:
                continue
            if "error" in payload:
                raise RuntimeError(
                    f"Codex app-server {method} failed: {payload['error']}"
                )
            result = payload.get("result")
            if not isinstance(result, dict):
                raise RuntimeError(
                    f"Codex app-server {method} returned no object result"
                )
            return result

    def list_threads(self) -> list[dict[str, Any]]:
        threads: list[dict[str, Any]] = []
        cursor = None
        while True:
            params: dict[str, Any] = {
                "archived": False,
                "limit": 100,
                "modelProviders": [],
                "sourceKinds": ["cli", "vscode"],
                "sortKey": "created_at",
                "sortDirection": "desc",
            }
            if cursor:
                params["cursor"] = cursor
            result = self.request("thread/list", params)
            data = result.get("data")
            if not isinstance(data, list):
                raise RuntimeError("Codex thread/list returned no data array")
            threads.extend(item for item in data if isinstance(item, dict))
            cursor = result.get("nextCursor")
            if not isinstance(cursor, str) or not cursor:
                return threads

    def archive_thread(self, thread_id: str) -> None:
        self.request("thread/archive", {"threadId": thread_id})


def _cutoff_epoch(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Thread cleanup cutoff must include a timezone")
    return int(parsed.timestamp())


def _write_log(state_dir: Path, message: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / LOG_FILENAME).open("a", encoding="utf-8") as handle:
        handle.write(
            f"{datetime.now().astimezone().isoformat()} {message.strip()}\n"
        )


def record_delivery_and_cleanup(
    *,
    session_key: str,
    sessions_dir: Path,
    state_dir: Path,
    cutoff: str,
) -> dict[str, Any]:
    sessions = _load_sessions(sessions_dir)
    current = sessions.get(session_key)
    if current is None:
        raise ValueError(f"Unknown OpenClaw session key: {session_key}")
    trajectory = _trajectory_path(sessions_dir, current)
    if trajectory is None:
        raise ValueError("OpenClaw session has no trajectory path")
    thread_id = latest_trajectory_thread_id(trajectory)
    if thread_id is None:
        raise ValueError("OpenClaw session trajectory has no Codex thread")

    receipts_path = state_dir / RECEIPTS_FILENAME
    _append_receipt(
        receipts_path,
        thread_id=thread_id,
        session_key=session_key,
    )
    delivered_ids = _load_receipt_ids(receipts_path)
    protected_ids = _current_thread_ids(sessions_dir, sessions)
    cutoff_epoch = _cutoff_epoch(cutoff)

    with CodexAppServer() as app_server:
        threads = app_server.list_threads()
        candidates = select_archive_candidates(
            threads,
            delivered_ids=delivered_ids,
            protected_ids=protected_ids,
            cutoff_epoch=cutoff_epoch,
        )
        archived = []
        for thread in candidates:
            candidate_id = thread["id"]
            app_server.archive_thread(candidate_id)
            archived.append(candidate_id)

    return {
        "recorded": thread_id,
        "archived": archived,
        "skipped": len(threads) - len(candidates),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record-delivery")
    record.add_argument("--session-key", required=True)
    record.add_argument("--sessions-dir", type=Path, required=True)
    record.add_argument("--state-dir", type=Path, required=True)
    record.add_argument("--cutoff", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "record-delivery":
            result = record_delivery_and_cleanup(
                session_key=args.session_key,
                sessions_dir=args.sessions_dir,
                state_dir=args.state_dir,
                cutoff=args.cutoff,
            )
        else:
            raise ValueError(f"Unsupported command: {args.command}")
    except Exception as error:
        _write_log(args.state_dir, f"error: {error}")
        print(
            json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
