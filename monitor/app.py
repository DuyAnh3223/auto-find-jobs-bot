import json
import logging
import os
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Thread
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from monitor.core import Group, Settings, group_url, post_url
from monitor.exporter import export_posts, local_time
from monitor.storage import Store
from monitor.worker import MonitorWorker


class MonitorApp(ctk.CTk):
    PAGE_SIZE = 100

    def __init__(self, data_dir: Path):
        super().__init__()
        self.title("Facebook Group Monitor · Feed fix 3")
        self.geometry("1220x850")
        self.minsize(1060, 740)
        self.data_dir = data_dir
        self.store = Store(data_dir / "monitor.db")
        self.settings = self.store.load_settings()
        self.worker = MonitorWorker(self.store, data_dir)
        self.export_thread = None
        self.export_events = SimpleQueue()
        self.closing = False
        self.next_scan = None
        self.offset = 0
        self.rows = {}
        self.edit_controls = []
        self.group_vars = []
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        self.build_results()
        self.refresh_results()
        self.after(200, self.poll_events)

    def build_sidebar(self):
        sidebar = ctk.CTkFrame(self, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(0, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)
        panel = ctk.CTkScrollableFrame(sidebar, width=300, corner_radius=0)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text="GROUP MONITOR", font=("Segoe UI", 23, "bold")).grid(
            row=0, column=0, padx=16, pady=(20, 0), sticky="w"
        )
        ctk.CTkLabel(panel, text="Theo dõi cơ hội từ những group bạn chọn", font=("Segoe UI", 12)).grid(
            row=1, column=0, padx=16, pady=(0, 15), sticky="w"
        )
        ctk.CTkLabel(panel, text="GROUPS", font=("Segoe UI", 14, "bold")).grid(
            row=2, column=0, sticky="w", padx=16
        )
        self.group_frame = ctk.CTkScrollableFrame(panel, height=155)
        self.group_frame.grid(row=3, column=0, padx=12, pady=8, sticky="ew")
        self.draw_groups()
        add = ctk.CTkButton(panel, text="+ Thêm group", command=self.add_group)
        add.grid(row=4, column=0, padx=16, pady=(0, 15), sticky="ew")
        self.edit_controls.append(add)
        ctk.CTkLabel(panel, text="TỪ KHÓA · mỗi dòng một cụm từ", font=("Segoe UI", 14, "bold")).grid(
            row=5, column=0, sticky="w", padx=16
        )
        self.keywords = ctk.CTkTextbox(panel, height=135, font=("Segoe UI", 14))
        self.keywords.grid(row=6, column=0, padx=16, pady=8, sticky="ew")
        self.keywords.insert("1.0", "\n".join(self.settings.keywords))
        self.edit_controls.append(self.keywords)
        options = ctk.CTkFrame(panel, fg_color="transparent")
        options.grid(row=7, column=0, padx=16, pady=8, sticky="ew")
        self.interval = ctk.StringVar(value=str(self.settings.interval_minutes))
        self.max_posts = ctk.StringVar(value=str(self.settings.max_posts))
        for index, (label, var) in enumerate(
            [("Quét mỗi (phút)", self.interval), ("Tối đa bài / group", self.max_posts)]
        ):
            ctk.CTkLabel(options, text=label).grid(row=index, column=0, sticky="w", pady=4)
            entry = ctk.CTkEntry(options, width=90, textvariable=var)
            entry.grid(row=index, column=1, padx=(20, 0), pady=4)
            self.edit_controls.append(entry)
        self.browser = ctk.StringVar(value="Edge" if self.settings.browser == "msedge" else "Chrome")
        ctk.CTkLabel(options, text="Trình duyệt").grid(row=2, column=0, sticky="w", pady=4)
        menu = ctk.CTkOptionMenu(options, values=["Edge", "Chrome"], variable=self.browser, width=90)
        menu.grid(row=2, column=1, padx=(20, 0), pady=4)
        self.edit_controls.append(menu)
        self.auto_export = ctk.BooleanVar(value=self.settings.auto_export)
        auto = ctk.CTkCheckBox(panel, text="Tự cập nhật Excel sau mỗi lượt", variable=self.auto_export)
        auto.grid(row=8, column=0, padx=16, pady=8, sticky="w")
        self.edit_controls.append(auto)
        save = ctk.CTkButton(
            panel, text="Lưu cấu hình", command=self.save_settings, fg_color="#475569", hover_color="#334155"
        )
        save.grid(row=9, column=0, padx=16, pady=8, sticky="ew")
        self.edit_controls.append(save)
        controls = ctk.CTkFrame(sidebar, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        controls.grid_columnconfigure(0, weight=1)
        self.login_button = ctk.CTkButton(
            controls, text="1. Mở Facebook để đăng nhập", command=self.start_login
        )
        self.login_button.grid(row=0, column=0, padx=16, pady=5, sticky="ew")
        self.edit_controls.append(self.login_button)
        self.confirm_button = ctk.CTkButton(
            controls, text="Đã đăng nhập", command=self.confirm_login, state="disabled"
        )
        self.confirm_button.grid(row=1, column=0, padx=16, pady=5, sticky="ew")
        actions = ctk.CTkFrame(controls, fg_color="transparent")
        actions.grid(row=2, column=0, padx=16, pady=12, sticky="ew")
        self.start_button = ctk.CTkButton(
            actions,
            text="START",
            width=135,
            command=self.start_scan,
            fg_color="#15803d",
            hover_color="#166534",
        )
        self.start_button.pack(side="left", padx=(0, 8))
        self.edit_controls.append(self.start_button)
        self.stop_button = ctk.CTkButton(
            actions,
            text="STOP",
            width=115,
            command=self.stop_scan,
            state="disabled",
            fg_color="#b91c1c",
            hover_color="#991b1b",
        )
        self.stop_button.pack(side="left")
        ctk.CTkLabel(
            controls,
            text="Máy cần bật và không ngủ.\nĐổi Chrome/Edge cần đăng nhập riêng.",
            justify="left",
            text_color=("#64748b", "#94a3b8"),
        ).grid(row=3, column=0, padx=16, pady=8, sticky="w")

    def draw_groups(self):
        for child in self.group_frame.winfo_children():
            child.destroy()
        self.group_vars = []
        self.group_controls = []
        for group in self.settings.groups:
            line = ctk.CTkFrame(self.group_frame, fg_color="transparent")
            line.pack(fill="x", pady=3)
            var = ctk.BooleanVar(value=group.enabled)
            check = ctk.CTkCheckBox(line, text=group.name[:27], variable=var, width=190)
            check.pack(side="left", fill="x", expand=True)
            remove = ctk.CTkButton(
                line, text="Xóa", width=45, command=lambda url=group.url: self.remove_group(url)
            )
            remove.pack(side="right")
            self.group_vars.append(var)
            self.group_controls.extend([check, remove])
        if not self.settings.groups:
            ctk.CTkLabel(self.group_frame, text="Chưa có group. Thêm link để bắt đầu.", wraplength=250).pack(
                pady=35
            )

    def sync_group_flags(self):
        for group, var in zip(self.settings.groups, self.group_vars):
            group.enabled = var.get()

    def add_group(self):
        value = ctk.CTkInputDialog(text="Link group Facebook:", title="Thêm group").get_input()
        if not value:
            return
        try:
            url = group_url(value)
            if any(g.url == url for g in self.settings.groups):
                raise ValueError("Group này đã có trong danh sách.")
        except ValueError as exc:
            messagebox.showerror("Link chưa hợp lệ", str(exc), parent=self)
            return
        name = ctk.CTkInputDialog(text="Tên hiển thị (có thể để trống):", title="Tên group").get_input()
        if name is None:
            return
        self.sync_group_flags()
        self.settings.groups.append(Group(name.strip() or url.rsplit("/", 1)[-1], url))
        self.draw_groups()

    def remove_group(self, url):
        self.sync_group_flags()
        self.settings.groups = [g for g in self.settings.groups if g.url != url]
        self.draw_groups()

    def read_settings(self, for_scan=False):
        self.sync_group_flags()
        try:
            interval, limit = int(self.interval.get()), int(self.max_posts.get())
        except ValueError:
            raise ValueError("Khoảng quét và số bài phải là số nguyên.") from None
        settings = Settings(
            groups=[Group(g.name, g.url, g.enabled) for g in self.settings.groups],
            keywords=self.keywords.get("1.0", "end").splitlines(),
            interval_minutes=interval,
            max_posts=limit,
            browser="msedge" if self.browser.get() == "Edge" else "chrome",
            auto_export=self.auto_export.get(),
        )
        settings.validate(for_scan)
        return settings

    def save_settings(self, for_scan=False):
        try:
            settings = self.read_settings(for_scan)
            self.store.save_settings(settings)
            self.settings = settings
            self.append_log("Đã lưu cấu hình.")
            return settings
        except (ValueError, OSError) as exc:
            messagebox.showerror("Không lưu được cấu hình", str(exc), parent=self)
            return None

    def set_busy(self, busy):
        for control in self.edit_controls + self.group_controls:
            control.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")
        self.confirm_button.configure(state="disabled")

    def start_login(self):
        settings = self.save_settings()
        if settings and self.worker.start(settings, "login"):
            self.set_busy(True)
            self.status.configure(text="Đang mở trình duyệt để đăng nhập…")

    def confirm_login(self):
        self.confirm_button.configure(state="disabled")
        self.worker.confirm_event.set()

    def start_scan(self):
        settings = self.save_settings(for_scan=True)
        if settings and self.worker.start(settings):
            self.set_busy(True)
            self.status.configure(text="Bắt đầu quét…")

    def stop_scan(self):
        self.worker.stop()
        self.next_scan = None
        self.status.configure(text="Đang dừng và đóng trình duyệt…")
        self.stop_button.configure(state="disabled")
        self.confirm_button.configure(state="disabled")

    def build_results(self):
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=0, column=1, padx=22, pady=18, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(panel, text="Bài đăng tìm được", font=("Segoe UI", 26, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.status = ctk.CTkLabel(
            panel, text="Sẵn sàng · đăng nhập Facebook trước lần quét đầu tiên", anchor="w"
        )
        self.status.grid(row=1, column=0, sticky="ew", pady=(3, 12))
        toolbar = ctk.CTkFrame(panel, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.search = ctk.CTkEntry(toolbar, placeholder_text="Tìm trong nội dung, group, từ khóa…")
        self.search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search.bind("<Return>", lambda _: self.search_results())
        ctk.CTkButton(toolbar, text="Tìm", width=55, command=self.search_results).pack(side="left", padx=3)
        self.export_buttons = []
        for label, suffix in [("Excel", ".xlsx"), ("CSV", ".csv")]:
            button = ctk.CTkButton(toolbar, text=label, width=65, command=lambda ext=suffix: self.export(ext))
            button.pack(side="left", padx=3)
            self.export_buttons.append(button)
        table_frame = ctk.CTkFrame(panel)
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            rowheight=36,
            font=("Segoe UI", 11),
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1e293b",
        )
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), padding=7)
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#0f172a")])
        self.table = ttk.Treeview(
            table_frame, columns=("time", "group", "keywords", "content"), show="headings"
        )
        for key, title, width in [
            ("time", "Ngày phát hiện", 155),
            ("group", "Group", 155),
            ("keywords", "Từ khóa", 170),
            ("content", "Nội dung", 270),
        ]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=70)
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table_frame, command=self.table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.bind("<<TreeviewSelect>>", self.show_details)
        self.table.bind("<Double-1>", self.open_post)
        nav = ctk.CTkFrame(panel, fg_color="transparent")
        nav.grid(row=4, column=0, sticky="ew", pady=8)
        self.total_label = ctk.CTkLabel(nav, text="")
        self.total_label.pack(side="left")
        self.next_button = ctk.CTkButton(nav, text="Sau →", width=75, command=lambda: self.change_page(1))
        self.next_button.pack(side="right", padx=3)
        self.prev_button = ctk.CTkButton(nav, text="← Trước", width=75, command=lambda: self.change_page(-1))
        self.prev_button.pack(side="right", padx=3)
        ctk.CTkButton(nav, text="Mở bài Facebook", width=130, command=self.open_post).pack(
            side="right", padx=8
        )
        self.details = ctk.CTkTextbox(panel, height=155, font=("Segoe UI", 13), wrap="word")
        self.details.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        self.set_text(self.details, "Chọn một bài để xem nội dung. Nhấp đúp để mở bài trên Facebook.")
        self.log = ctk.CTkTextbox(panel, height=105, font=("Consolas", 11), wrap="word")
        self.log.grid(row=6, column=0, sticky="ew")
        self.log.configure(state="disabled")
        ctk.CTkButton(
            panel,
            text="Mở thư mục dữ liệu / Excel",
            command=lambda: os.startfile(str(self.data_dir)),
            fg_color="#475569",
            hover_color="#334155",
        ).grid(row=7, column=0, sticky="w", pady=(10, 0))

    @staticmethod
    def set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", f"{datetime.now():%H:%M:%S}  {text}\n")
        if int(self.log.index("end-1c").split(".")[0]) > 300:
            self.log.delete("1.0", "100.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def search_results(self):
        self.offset = 0
        self.refresh_results()

    def change_page(self, direction):
        self.offset = max(0, self.offset + direction * self.PAGE_SIZE)
        self.refresh_results()

    def refresh_results(self):
        search = self.search.get().strip()
        total = self.store.count(search)
        if self.offset >= total:
            self.offset = max(0, ((total - 1) // self.PAGE_SIZE) * self.PAGE_SIZE)
        rows = self.store.posts(search, self.PAGE_SIZE, self.offset)
        selected = self.table.selection()
        self.rows = {str(row["id"]): row for row in rows}
        for item in self.table.get_children():
            self.table.delete(item)
        for key, row in self.rows.items():
            self.table.insert(
                "",
                "end",
                iid=key,
                values=(
                    local_time(row["detected_at"])[:19],
                    row["group_name"],
                    ", ".join(json.loads(row["keywords"])),
                    " ".join(row["content"].split())[:180],
                ),
            )
        if selected and selected[0] in self.rows:
            self.table.selection_set(selected[0])
        else:
            self.set_text(self.details, "Chọn một bài để xem nội dung. Nhấp đúp để mở bài trên Facebook.")
        self.total_label.configure(
            text=f"{total} bài · {self.offset + 1 if total else 0}–{self.offset + len(rows)}"
        )
        self.prev_button.configure(state="normal" if self.offset else "disabled")
        self.next_button.configure(state="normal" if self.offset + len(rows) < total else "disabled")

    def selected_row(self):
        selection = self.table.selection()
        return self.rows.get(selection[0]) if selection else None

    def show_details(self, _event=None):
        row = self.selected_row()
        if row:
            self.set_text(
                self.details,
                f"{row['group_name']} · {', '.join(json.loads(row['keywords']))}\n"
                f"{row['url']}\nNgày đăng: {local_time(row['posted_at']) or row['posted_time_raw'] or 'Không xác định'}"
                f"\nPhát hiện: {local_time(row['detected_at'])}\n\n{row['content']}",
            )

    def open_post(self, _event=None):
        if _event is not None:
            item = self.table.identify_row(_event.y)
            if not item:
                return
            self.table.selection_set(item)
        row = self.selected_row()
        if row and post_url(row["url"], row["group_url"]):
            webbrowser.open(row["url"])

    def export(self, suffix):
        if self.export_thread and self.export_thread.is_alive():
            return
        filename = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=suffix,
            initialfile=f"facebook-posts-{datetime.now():%Y%m%d-%H%M}{suffix}",
            filetypes=[("Excel" if suffix == ".xlsx" else "CSV", "*" + suffix)],
        )
        if not filename:
            return
        search = self.search.get().strip()
        if (
            Path(filename).resolve() == (self.data_dir / "exports" / "results.xlsx").resolve()
            and self.worker.running
        ):
            messagebox.showerror(
                "File đang được tự cập nhật", "Hãy chọn tên file khác khi bot đang chạy.", parent=self
            )
            return
        for button in self.export_buttons:
            button.configure(state="disabled")

        def run():
            try:
                rows = self.store.posts(search)
                export_posts(rows, Path(filename))
                self.export_events.put(("log", f"Đã xuất {len(rows)} bài: {filename}"))
            except Exception as exc:
                self.export_events.put(("error", f"Không xuất được file: {exc}"))

        self.export_thread = Thread(target=run, name="export")
        self.export_thread.start()

    def poll_events(self):
        refresh = False
        for queue in (self.worker.events, self.export_events):
            while True:
                try:
                    kind, value = queue.get_nowait()
                except Empty:
                    break
                if kind == "results":
                    refresh = True
                elif kind == "finished":
                    self.next_scan = None
                    self.status.configure(text="Đã dừng · xem nhật ký bên dưới nếu có lỗi")
                    self.set_busy(False)
                elif kind == "waiting":
                    self.next_scan = value
                elif kind == "status":
                    self.next_scan = None
                    self.status.configure(text=value)
                elif kind == "login_ready":
                    self.status.configure(text="Hoàn tất đăng nhập trong trình duyệt, rồi bấm ‘Đã đăng nhập’")
                    self.confirm_button.configure(state="normal")
                    self.append_log(value)
                else:
                    self.append_log(value)
                    if kind == "error" and not self.closing:
                        messagebox.showerror("Thông báo", value, parent=self)
        if refresh:
            self.refresh_results()
        if self.next_scan:
            seconds = max(0, int(self.next_scan - time.time()))
            self.status.configure(
                text=f"Đang chờ · lượt tiếp theo sau {seconds // 60:02d}:{seconds % 60:02d}"
            )
        if not self.export_thread or not self.export_thread.is_alive():
            for button in self.export_buttons:
                button.configure(state="normal")
        if (
            self.closing
            and not self.worker.running
            and not (self.export_thread and self.export_thread.is_alive())
        ):
            self.destroy()
            return
        self.after(200, self.poll_events)

    def close_app(self):
        if self.closing:
            return
        # Persist pending edits on normal exit; invalid input stays visible for correction.
        if not self.worker.running and self.save_settings() is None:
            return
        self.closing = True
        self.stop_scan()
        self.set_busy(True)
        self.stop_button.configure(state="disabled")

    def report_callback_exception(self, exception, value, traceback):
        logging.error("GUI callback failed", exc_info=(exception, value, traceback))
        messagebox.showerror("Lỗi ứng dụng", str(value), parent=self)
