"""Read-only full-volume comparison with the frozen prototype and prior pilot.

Development qualification only: executes trusted source from the supplied local
prototype checkout and baseline git revision. Output arrays must agree exactly.
"""

import argparse
from contextlib import nullcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
from unittest.mock import patch

import h5py
import numpy as np

from tofscope.api.app import build_services
from tofscope.application.commands import CommandEnvelope
from tofscope.application.jobs import IntegrationSpec
from tofscope.application.resources import ResourceBudget
from tofscope.config import Settings
from tofscope.science.integration import custom_peak_windows


def baseline_module(name, path, ref):
    source = subprocess.check_output(
        ["git", "show", ref + ":" + path], text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, path, "exec"), module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--prototype", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=1301)
    parser.add_argument("--baseline-ref", default="967e5cb")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.file.resolve()
    if args.output.resolve() == source:
        raise ValueError("Qualification output must not replace the acquisition.")
    before = source.stat()
    with h5py.File(source, "r") as file:
        shape = file["PeakData/PeakData"].shape
    if not 0 < args.frames <= shape[0]:
        raise ValueError("Select a positive frame count within the stored domain.")
    output_bytes = args.frames * shape[1] * shape[2] * 4

    # Do not create bytecode in the frozen checkout. Only the undecorated read
    # runs, avoiding the prototype's adjacent acquisition lock-file policy.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.prototype.resolve()))
    spec = importlib.util.spec_from_file_location(
        "frozen_integration", args.prototype / "integration.py"
    )
    prototype = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prototype)
    old_events = baseline_module(
        "old_events", "src/tofscope/storage/bounded_events.py", args.baseline_ref
    )
    old_integration = baseline_module(
        "old_integration", "src/tofscope/science/integration.py", args.baseline_ref
    )
    results = {}
    expected = None
    windows = [(26.5, 27.5)]
    with tempfile.TemporaryDirectory(prefix="tofscope-full-integration-") as runtime:
        settings = Settings(source.parent, runtime_dir=Path(runtime))
        modes = [
            ("prototype", prototype.custom_peak_windows),
            ("previous_pilot", old_integration.custom_peak_windows),
            ("pooled_pilot", custom_peak_windows),
        ]
        for mode, function in modes:
            budget = ResourceBudget(settings)
            peak, requests = 0, 0

            def reserve(size):
                nonlocal peak, requests
                lease = budget.reserve("qualification", "qualification", size)
                peak = max(peak, budget.physical_bytes)
                requests += 1
                return lease

            def progress(done, total):
                if done % 256 == 0 or done == total:
                    print(json.dumps(dict(
                        mode=mode, done=done, total=total,
                        elapsed_s=round(time.perf_counter() - start, 3),
                    )), flush=True)

            with reserve(output_bytes):
                kwargs = {} if mode == "prototype" else {"reserve": reserve}
                context = (
                    patch("tofscope.storage.bounded_events.admitted_events",
                          old_events.admitted_events)
                    if mode == "previous_pilot" else nullcontext()
                )
                with context:
                    start = time.perf_counter()
                    volume = function.__wrapped__(
                        source, windows, 0, args.frames - 1,
                        progress=progress, **kwargs,
                    )
                    elapsed = time.perf_counter() - start
                if expected is None:
                    expected = volume
                else:
                    np.testing.assert_array_equal(volume, expected)
                results[mode] = dict(
                    seconds=elapsed, frames=args.frames, managed_peak_bytes=peak,
                    managed_scratch_accounted=mode != "prototype",
                    reservation_calls=requests,
                    sha256=hashlib.sha256(volume).hexdigest(), exact_equal=True,
                )
                print(json.dumps({"mode": mode, **results[mode]}), flush=True)
            assert budget.physical_bytes == 0
            if mode != "prototype":
                del volume

        services = build_services(settings)
        try:
            owner = "qualification"
            workspace = services.workspaces.create(owner)
            dataset = services.repository.open(owner, source.name)
            analysis = services.workspaces.create_analysis(owner, workspace.id, dataset)
            start = time.perf_counter()
            job = services.jobs.submit(
                owner, analysis.id,
                CommandEnvelope("full-job", analysis.revision, dataset.generation,
                                {"type": "set_depth", "depth": {"mode": "all"}}),
                IntegrationSpec(tuple(windows), (0, args.frames - 1), "Performance signal"),
            )
            result = services.jobs.wait(owner, job.id, timeout=180)
            elapsed = time.perf_counter() - start
            assert result.status == "succeeded", result
            state = services.workspaces.get(owner, analysis.id)
            assert state.revision == analysis.revision + 2 and result.done == args.frames
            with services.cache.load(
                owner, analysis.id, state.dataset, next(row.recipe for row in state.signals if row.id == job.signal_id)
            ) as lease:
                np.testing.assert_array_equal(lease.array, expected)
            results["service_job"] = dict(
                seconds=elapsed, status=result.status, done=result.done,
                total=result.total, exact_equal=True, revision=state.revision,
            )
            print(json.dumps({"mode": "service_job", **results["service_job"]}), flush=True)
        finally:
            services.workspaces.close_all()
            services.jobs.shutdown()
        assert services.cache.budget.physical_bytes == 0

    after = source.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_ino, after.st_size, after.st_mtime_ns
    )
    results.update(source_unchanged=True, intervals=windows, file=source.name,
                   baseline_ref=args.baseline_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results), flush=True)


if __name__ == "__main__":
    main()
