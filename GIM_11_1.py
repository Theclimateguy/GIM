"""Compatibility wrapper for GIM_11_1 package entrypoint."""

from gim_11_1 import *  # noqa: F401,F403
from gim_11_1.cli import main


if __name__ == "__main__":
    main()
