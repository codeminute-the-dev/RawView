from __future__ import annotations

import os
import sys

from rawview.qt_ui import run_qt_app


def _argv_no_agent_flag() -> bool:
    env = os.environ.get("RAWVIEW_NO_AGENT", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    return "--no-agent" in sys.argv


def _strip_no_agent_argv() -> None:
    if "--no-agent" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--no-agent"]


def main() -> None:
    no = _argv_no_agent_flag()
    _strip_no_agent_argv()
    raise SystemExit(run_qt_app(no_agent=no))


def main_re() -> None:
    """RawView without the in-app Anthropic agent (manual Ghidra RE; use Cursor chat for AI help)."""
    raise SystemExit(run_qt_app(no_agent=True))


if __name__ == "__main__":
    main()
