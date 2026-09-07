import argparse
import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Facebook Group Monitor")
    parser.add_argument("--data-dir", type=Path, help="Override app data directory")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Open hidden GUI, verify widgets, exit without Facebook"
    )
    args = parser.parse_args()
    if args.smoke_test and not args.data_dir:
        args.data_dir = Path(tempfile.mkdtemp(prefix="group-monitor-smoke-"))
    data_dir = (
        args.data_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FacebookGroupMonitor"
    ).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            RotatingFileHandler(
                data_dir / "logs" / "monitor.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
        ],
    )
    # Hold this file handle until exit: protects both browser profile and scheduler across processes.
    lock = open(data_dir / "app.lock", "a+b")
    try:
        import msvcrt

        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, "Ứng dụng đã mở với thư mục dữ liệu này.", "Facebook Group Monitor", 0x40
            )
            return 1

        import customtkinter as ctk

        from monitor.app import MonitorApp

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        app = MonitorApp(data_dir)
        if args.smoke_test:
            from monitor.smoke import verify_runtime

            app.withdraw()
            app.update_idletasks()
            app.store.save_settings(app.read_settings())
            app.refresh_results()
            verify_runtime(data_dir)
            app.after(400, app.close_app)
        app.mainloop()
        if args.smoke_test:
            (data_dir / "smoke-ok.txt").write_text(
                "GUI, SQLite, Excel and Playwright/Edge passed", encoding="utf-8"
            )
        return 0
    except Exception as exc:
        logging.exception("Application startup failed")
        if args.smoke_test:
            raise
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0, f"Không mở được ứng dụng: {exc}\nLog: {data_dir / 'logs'}", "Facebook Group Monitor", 0x10
        )
        return 1
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
