import logging
import time
from pathlib import Path
from queue import SimpleQueue
from threading import Event, Thread

from monitor.exporter import export_posts
from monitor.facebook import ScanStopped, SessionRequired, check_stop, login, open_browser, read_group


class MonitorWorker:
    def __init__(self, store, data_dir: Path):
        self.store = store
        self.data_dir = data_dir
        self.events = SimpleQueue()
        self.stop_event = Event()
        self.confirm_event = Event()
        self.thread = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def emit(self, kind, message):
        if kind in {"log", "error", "login_ready"}:
            logging.info("%s: %s", kind, message)
        self.events.put((kind, message))

    def start(self, settings, mode="scan"):
        if self.running:
            return False
        self.stop_event.clear()
        self.confirm_event.clear()
        self.thread = Thread(target=self._run, args=(settings, mode), name="facebook-monitor")
        self.thread.start()
        return True

    def stop(self):
        self.stop_event.set()

    def _run(self, settings, mode):
        try:
            if mode == "login":
                login(self.data_dir, settings.browser, self.stop_event, self.confirm_event, self.emit)
            else:
                while not self.stop_event.is_set():
                    started = time.monotonic()
                    self.scan_once(settings)
                    if self.stop_event.is_set():
                        break
                    # Start-to-start interval; overdue scans wait a full interval to avoid catch-up bursts.
                    remaining = settings.interval_minutes * 60 - (time.monotonic() - started)
                    if remaining <= 0:
                        remaining = settings.interval_minutes * 60
                    self.emit("waiting", time.time() + remaining)
                    if self.stop_event.wait(remaining):
                        break
        except ScanStopped:
            self.emit("log", "Đã dừng theo yêu cầu. Các bài đã lưu vẫn được giữ lại.")
        except SessionRequired as exc:
            self.emit("error", str(exc))
        except Exception as exc:
            logging.exception("Worker failed")
            self.emit("error", f"Đã dừng: {exc}")
        finally:
            self.emit("finished", "Đã dừng")

    def scan_once(self, settings):
        self.emit("status", "Đang quét…")
        count, failures, successes, saved = 0, 0, 0, 0

        def save(post):
            nonlocal count, saved
            if self.store.save_post(post):
                count += 1
            saved += 1
            self.emit("results", "")

        with open_browser(self.data_dir, settings.browser) as context:
            for group in settings.groups:
                check_stop(self.stop_event)
                if not group.enabled:
                    continue
                self.emit("status", f"Đang đọc: {group.name}")
                try:
                    read_group(
                        context,
                        group,
                        settings.keywords,
                        settings.max_posts,
                        self.stop_event,
                        self.emit,
                        save,
                    )
                    successes += 1
                except (ScanStopped, SessionRequired):
                    raise
                except Exception as exc:
                    failures += 1
                    logging.exception("Group scan failed: %s", group.url)
                    self.emit("log", f"Lỗi group {group.name}: {exc}")
        self.emit("log", f"Kết thúc lượt quét: {count} bài mới; {failures} group lỗi.")
        if not successes and not saved:
            self.emit(
                "log",
                "Không có group nào đọc thành công. Giữ nguyên file Excel; cần kiểm tra lỗi đọc Facebook.",
            )
            return
        if failures and saved:
            self.emit(
                "log",
                f"Lượt quét chưa đầy đủ; đã lưu/cập nhật {saved} bài khớp. Excel vẫn nhận các bài đã lưu.",
            )
        if settings.auto_export:
            try:
                target = self.data_dir / "exports" / "results.xlsx"
                export_posts(self.store.posts(), target)
                self.emit("log", f"Đã cập nhật Excel: {target}")
            except Exception as exc:
                self.emit(
                    "log",
                    f"Xuất Excel thất bại (SQLite đã lưu): {exc}. "
                    "Nếu file đang mở trong Excel, hãy đóng file trước lượt tiếp theo.",
                )
