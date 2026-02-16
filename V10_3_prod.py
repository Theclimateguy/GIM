"""Compatibility wrapper for V10.3 package entrypoint."""

from v10_3_prod import *  # noqa: F401,F403
from v10_3_prod.cli import main


if __name__ == "__main__":
    main()
