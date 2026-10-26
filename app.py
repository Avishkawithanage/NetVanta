"""NetVanta entry point."""

import sys

from netvanta.utils.logging_setup import setup_logging


def main() -> int:
    if sys.platform != "win32":
        print("NetVanta supports Windows 10/11 only.")
        return 1
    log = setup_logging()
    try:
        from netvanta.ui.main_window import run

        return run(smoke="--smoke-test" in sys.argv)
    except Exception:
        log.exception("Fatal error")
        try:
            from tkinter import messagebox

            messagebox.showerror("NetVanta", "NetVanta hit an unexpected error. See the log file in %APPDATA%\\NetVanta.")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
