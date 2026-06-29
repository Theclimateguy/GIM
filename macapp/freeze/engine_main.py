"""PyInstaller entry point: the GIM17 engine sidecar as a frozen, self-contained
binary (no system Python / repo needed). Bundled data (data/, scenarios/) is
unpacked next to the `gim` package so runtime.REPO_ROOT resolves inside the bundle.
"""
from gim.engine_service import run_engine_service

if __name__ == "__main__":
    run_engine_service(host="127.0.0.1", port=0)
