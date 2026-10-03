# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

"""Run every native role comparison inside the existing aggregate CTest deadline."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import re
import signal
import subprocess
import threading
import time

CLASS_IDS = ("Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer")
MONSTER_IDS = ("Gooby", "Pritz", "OctoBogz", "PritzMage", "GoblinThief", "Cultist", "CultLeader")
MAX_WORKERS = 4
TOTAL_SECONDS = 55


@dataclass
class WorkerResult:
    name: str
    return_code: int
    stdout: list
    complete_streams: bool


def emitLine(line):
    print(line, flush=True)


def runWorker(command, name, deadline, emit, output_lock, cancelled):
    stdout = []
    if cancelled.is_set() or time.monotonic() >= deadline:
        return WorkerResult(name, -1, stdout, False)
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace"
    )
    stream_eof = [False, False]
    reader_errors = []

    def readerError(index, error):
        message = f"stream {index}: {type(error).__name__}: {error}"
        reader_errors.append(message)
        with output_lock:
            emit(f"[{name}] FAILED: cannot drain native output: {message}")

    def drain(stream, captured, index):
        try:
            for line in stream:
                if captured is not None:
                    captured.append(line.rstrip("\r\n"))
                with output_lock:
                    emit(f"[{name}] {line.rstrip()}")
            stream_eof[index] = True
        except Exception as error:
            readerError(index, error)
        finally:
            try:
                stream.close()
            except Exception as error:
                readerError(index, error)

    readers = [
        threading.Thread(target=drain, args=(process.stdout, stdout, 0), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, None, 1), daemon=True),
    ]
    for reader in readers:
        reader.start()
    return_code = -1
    try:
        while not cancelled.is_set() and time.monotonic() < deadline:
            try:
                return_code = process.wait(timeout=min(0.1, max(0, deadline - time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                pass
        if return_code == -1:
            with output_lock:
                emit(f"[{name}] FAILED: aggregate role deadline or cancellation")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        for reader in readers:
            reader.join(timeout=0.5)
    complete_streams = all(not reader.is_alive() for reader in readers) and all(stream_eof) and not reader_errors
    return WorkerResult(name, return_code, stdout, complete_streams)


def validateWorker(result):
    if result.return_code != 0 or not result.complete_streams:
        return False
    rows = []
    completions = []
    for line in result.stdout:
        match = re.match(r"role balance (\w+)/(\w+) hp ", line)
        if match:
            rows.append(match.groups())
        if line.startswith("role class complete "):
            completions.append(line)
    return rows == [(result.name, monster_id) for monster_id in MONSTER_IDS] and completions == [
        f"role class complete {result.name} rows=7 pairedSeeds=77 fights=154"
    ]


def runMatrix(command_prefix, timeout=TOTAL_SECONDS, workers=MAX_WORKERS, emit=emitLine):
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError("role matrix requires one to four workers")
    deadline = time.monotonic() + timeout
    output_lock = threading.Lock()
    cancelled = threading.Event()
    contracts = runWorker([*command_prefix, "--contracts-only"], "contracts", deadline, emit, output_lock, cancelled)
    if (
        contracts.return_code != 0
        or not contracts.complete_streams
        or contracts.stdout.count("role contracts complete") != 1
    ):
        emit("FAILED: common native role contracts did not complete successfully")
        return 1
    results = {}
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        pending = {
            pool.submit(
                runWorker, [*command_prefix, "--role-class", class_id], class_id, deadline, emit, output_lock, cancelled
            )
            for class_id in CLASS_IDS
        }
        for future in as_completed(pending):
            result = future.result()
            results[result.name] = result
    finally:
        cancelled.set()
        pool.shutdown(wait=True)
    if set(results) != set(CLASS_IDS) or not all(validateWorker(result) for result in results.values()):
        emit("FAILED: all five classes, 35 rows and 770 native fights must complete with every assertion passing")
        return 1
    emit("role matrix complete classes=5 rows=35 pairedSeeds=385 fights=770 commonContracts=1")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", help="The configured native monster_balance_unit_tests executable")
    args = parser.parse_args()

    def terminate(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    return runMatrix([args.executable])


if __name__ == "__main__":
    raise SystemExit(main())
