"""PyInstaller entry for the frozen v2 engine sidecar.

Runs the deterministic gim2 engine exactly as ``python3 -m gim2 engine`` does, so
the frozen binary prints the same ``gim-engine/2`` ready-line the app expects.
"""

import multiprocessing

if __name__ == "__main__":
    # Must precede any pool use in the frozen binary; harmless otherwise. The
    # ensemble pool forces a fork context (see gim2.scenario.run_trajectories) so a
    # frozen onefile is not re-extracted per worker.
    multiprocessing.freeze_support()
    try:
        multiprocessing.set_start_method("fork")
    except (RuntimeError, ValueError):
        pass

    from gim2.engine_service import run_engine_service

    run_engine_service()
