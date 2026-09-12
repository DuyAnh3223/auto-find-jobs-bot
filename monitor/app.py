import json
import logging
import os
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Thread
from tkinter import PanedWindow, filedialog, messagebox, ttk

import customtkinter as ctk

from monitor.core import Group, Settings, group_url, post_url
from monitor.exporter import export_posts, local_time
from monitor.storage import Store
from monitor.tooltip import LinkTooltip
from monitor.worker import MonitorWorker


class MonitorApp(ctk.CTk):
    PAGE_SIZE = 100

    def __init__(self, data_dir: Path):
        super().__init__()
        self.title("Facebook Group Monitor · Theo dõi ứng tuyển")
        self.geometry(
            f"{min(1440, self.winfo_screenwidth() - 60)}x{min(850, self.winfo_screenheight() - 80)}"
        )
        self.minsize(1060, 680)
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
        self.tracker = None
        self.saved_panel = None
        self.checks_panel = None
        self.post_undo = []
        self.edit_controls = []
        self.group_vars = []
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        self.build_results()
        self.refresh_results()
        self.bind_all("<KeyPress-q>", lambda event: self.handle_post_shortcut(event, -1))
        self.bind_all("<KeyPress-e>", lambda event: self.handle_post_shortcut(event, 1))
        self.bind_all(
            "<KeyPress-y>", lambda event: self.handle_post_action_shortcut(event, self.save_for_consideration)
        )
        self.bind_all(
            "<KeyPress-d>", lambda event: self.handle_post_action_shortcut(event, self.mark_skipped)
        )
        self.bind_all("<KeyPress-o>", self.handle_open_post_shortcut)
        self.bind_all("<Control-s>", self.handle_ctrl_s)
        self.bind_all("<Control-z>", self.handle_ctrl_z)
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
        ctk.CTkLabel(panel, text="VỊ TRÍ / CÔNG NGHỆ · OR", font=("Segoe UI", 14, "bold")).grid(
            row=5, column=0, sticky="w", padx=16
        )
        self.keywords = ctk.CTkTextbox(panel, height=135, font=("Segoe UI", 14))
        self.keywords.grid(row=6, column=0, padx=16, pady=8, sticky="ew")
        self.keywords.insert("1.0", "\n".join(self.settings.keywords))
        self.edit_controls.append(self.keywords)
        self.location_box = self._criteria_box(panel, "ĐỊA ĐIỂM · OR", self.settings.location_keywords, 7)
        self.location_box.delete("1.0", "end")
        self.location_box.insert("1.0", "HCM · TP.HCM · Hồ Chí Minh · Sài Gòn\nNgoài HCM tự bỏ qua; chưa rõ địa điểm xem riêng.")
        self.location_box.configure(state="disabled")
        self.edit_controls.remove(self.location_box)
        self.experience_box = self._criteria_box(
            panel, "KINH NGHIỆM · OR", self.settings.experience_keywords, 9
        )
        options = ctk.CTkFrame(panel, fg_color="transparent")
        options.grid(row=11, column=0, padx=16, pady=8, sticky="ew")
        self.interval = ctk.StringVar(value=str(self.settings.interval_minutes))
        self.max_posts = ctk.StringVar(value=str(self.settings.max_posts))
        self.deep_time = ctk.StringVar(value=self.settings.daily_deep_time)
        self.deep_posts = ctk.StringVar(value=str(self.settings.daily_deep_posts))
        for index, (label, var) in enumerate(
            [
                ("Quét thường mỗi (phút)", self.interval),
                ("Bài / group lượt thường", self.max_posts),
                ("Bài / group khi mở bot", self.deep_posts),
            ]
        ):
            ctk.CTkLabel(options, text=label).grid(row=index, column=0, sticky="w", pady=4)
            entry = ctk.CTkEntry(options, width=90, textvariable=var)
            entry.grid(row=index, column=1, padx=(20, 0), pady=4)
            self.edit_controls.append(entry)
        self.browser = ctk.StringVar(value="Edge" if self.settings.browser == "msedge" else "Chrome")
        ctk.CTkLabel(options, text="Trình duyệt").grid(row=4, column=0, sticky="w", pady=4)
        menu = ctk.CTkOptionMenu(options, values=["Edge", "Chrome"], variable=self.browser, width=90)
        menu.grid(row=4, column=1, padx=(20, 0), pady=4)
        self.edit_controls.append(menu)
        self.auto_export = ctk.BooleanVar(value=self.settings.auto_export)
        auto = ctk.CTkCheckBox(panel, text="Tự cập nhật Excel sau mỗi lượt", variable=self.auto_export)
        auto.grid(row=12, column=0, padx=16, pady=8, sticky="w")
        self.edit_controls.append(auto)
        save = ctk.CTkButton(
            panel, text="Lưu cấu hình", command=self.save_settings, fg_color="#475569", hover_color="#334155"
        )
        save.grid(row=13, column=0, padx=16, pady=8, sticky="ew")
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
            check = ctk.CTkCheckBox(line, text="", variable=var, width=24)
            check.grid(row=0, column=0, sticky="nw", pady=4)
            line.grid_columnconfigure(1, weight=1)
            name = ctk.CTkLabel(line, text=group.name, wraplength=175, justify="left",
                               anchor="w", cursor="hand2")
            name.grid(row=0, column=1, sticky="ew", padx=(4, 6))
            name.bind("<Double-Button-1>", lambda event, url=group.url: self.open_group(url))
            name.link_tooltip = LinkTooltip(name, group.url)
            remove = ctk.CTkButton(
                line, text="Xóa", width=45, command=lambda url=group.url: self.remove_group(url)
            )
            remove.grid(row=0, column=2, sticky="ne", pady=4)
            self.group_vars.append(var)
            self.group_controls.extend([check, remove])
        if not self.settings.groups:
            ctk.CTkLabel(self.group_frame, text="Chưa có group. Thêm link để bắt đầu.", wraplength=250).pack(
                pady=35
            )

    def open_group(self, url):
        webbrowser.open(group_url(url))

    def _criteria_box(self, panel, title, values, row):
        ctk.CTkLabel(panel, text=title, font=("Segoe UI", 13, "bold")).grid(
            row=row, column=0, sticky="w", padx=16, pady=(4, 0)
        )
        box = ctk.CTkTextbox(panel, height=76, font=("Segoe UI", 13))
        box.grid(row=row + 1, column=0, padx=16, pady=5, sticky="ew")
        box.insert("1.0", "\n".join(values))
        self.edit_controls.append(box)
        return box

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
            deep_posts = int(self.deep_posts.get())
        except ValueError:
            raise ValueError("Khoảng quét và số bài phải là số nguyên.") from None
        settings = Settings(
            groups=[Group(g.name, g.url, g.enabled) for g in self.settings.groups],
            keywords=self.keywords.get("1.0", "end").splitlines(),
            location_keywords=self.settings.location_keywords,
            experience_keywords=self.experience_box.get("1.0", "end").splitlines(),
            interval_minutes=interval,
            max_posts=limit,
            daily_deep_time=self.deep_time.get().strip(),
            daily_deep_posts=deep_posts,
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
        self.results_panel = panel
        panel.grid(row=0, column=1, padx=22, pady=18, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(panel, text="Bài đăng", font=("Segoe UI", 26, "bold")).grid(row=0, column=0, sticky="w")
        self.status = ctk.CTkLabel(
            panel, text="Sẵn sàng · đăng nhập Facebook trước lần quét đầu tiên", anchor="w"
        )
        self.status.grid(row=1, column=0, sticky="ew", pady=(3, 12))
        self.checks_button = ctk.CTkButton(
            panel, text=f"Kiểm tra group ({len(self.store.scan_checks())})", command=self.open_checks
        )
        self.checks_button.grid(row=0, column=0, sticky="e")
        tabs = ctk.CTkFrame(panel, fg_color="transparent")
        tabs.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(tabs, text="Bài lưu xem xét", command=self.open_saved_considerations).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        ctk.CTkButton(tabs, text="Theo dõi ứng tuyển", command=self.open_tracker).grid(
            row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 8))
        ctk.CTkLabel(tabs, text="Địa điểm").grid(row=1, column=0, padx=(0, 5))
        self.location_filter = ctk.CTkOptionMenu(
            tabs, values=["HCM", "Chưa rõ địa điểm", "Tất cả"], width=150,
            command=lambda _: self.search_results(),
        )
        self.location_filter.grid(row=1, column=1)
        ctk.CTkLabel(tabs, text="Đánh giá").grid(row=1, column=2, padx=(12, 5))
        self.evaluation_filter = ctk.CTkOptionMenu(
            tabs,
            values=["Tất cả", "Phù hợp", "Cần xem lại"],
            width=120,
            command=lambda _: self.search_results(),
        )
        self.evaluation_filter.grid(row=1, column=3)
        ctk.CTkLabel(tabs, text="Xử lý").grid(row=1, column=4, padx=(12, 5))
        self.processing_filter = ctk.CTkOptionMenu(
            tabs,
            values=["Chưa xử lý", "Đã lưu xem xét", "Đang theo dõi", "Đã bỏ qua", "Tất cả"],
            width=120,
            command=lambda _: self.search_results(),
        )
        self.processing_filter.grid(row=1, column=5)
        toolbar = ctk.CTkFrame(panel, fg_color="transparent")
        toolbar.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.search = ctk.CTkEntry(toolbar, placeholder_text="Tìm trong nội dung, group, từ khóa…")
        self.search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search.bind("<Return>", lambda _: self.search_results())
        ctk.CTkButton(toolbar, text="Tìm", width=55, command=self.search_results).pack(side="left", padx=3)
        self.export_buttons = []
        for label, suffix in [("Excel", ".xlsx"), ("CSV", ".csv")]:
            button = ctk.CTkButton(toolbar, text=label, width=65, command=lambda ext=suffix: self.export(ext))
            button.pack(side="left", padx=3)
            self.export_buttons.append(button)
        self.reading_panes = PanedWindow(
            panel, orient="horizontal", sashwidth=8, background="#dbe2ea", borderwidth=0, opaqueresize=True
        )
        self.reading_panes.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
        list_panel = ctk.CTkFrame(self.reading_panes, corner_radius=0)
        list_panel.grid_columnconfigure(0, weight=1)
        list_panel.grid_rowconfigure(0, weight=1)
        detail_panel = ctk.CTkFrame(self.reading_panes, corner_radius=0)
        detail_panel.grid_columnconfigure(0, weight=1)
        detail_panel.grid_rowconfigure(1, weight=1)
        self.reading_panes.add(list_panel, minsize=280, width=390, stretch="always")
        self.reading_panes.add(detail_panel, minsize=300, width=520, stretch="always")
        table_frame = ctk.CTkFrame(list_panel)
        table_frame.grid(row=0, column=0, sticky="nsew")
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
            table_frame, columns=("application", "evaluation", "time", "group", "keywords"), show="headings"
        )
        self.table.tag_configure("applied", background="#dcfce7", foreground="#166534")
        self.table.tag_configure("review", background="#fef3c7", foreground="#92400e")
        for key, title, width in [
            ("application", "Theo dõi", 155),
            ("evaluation", "Đánh giá", 125),
            ("time", "Ngày phát hiện", 145),
            ("group", "Group", 90),
            ("keywords", "Từ khóa", 155),
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
        nav = ctk.CTkFrame(list_panel, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=6, pady=8)
        self.total_label = ctk.CTkLabel(nav, text="")
        self.total_label.pack(side="left")
        self.next_button = ctk.CTkButton(nav, text="Sau →", width=75, command=lambda: self.change_page(1))
        self.next_button.pack(side="right", padx=3)
        self.prev_button = ctk.CTkButton(nav, text="← Trước", width=75, command=lambda: self.change_page(-1))
        self.prev_button.pack(side="right", padx=3)
        detail_header = ctk.CTkFrame(detail_panel, fg_color="transparent")
        detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        ctk.CTkLabel(detail_header, text="Nội dung bài đăng", font=("Segoe UI", 17, "bold")).pack(side="left")
        ctk.CTkButton(
            detail_header,
            text="Tạo hồ sơ ứng tuyển",
            width=155,
            command=self.create_application_from_post,
        ).pack(side="right", padx=6)
        ctk.CTkButton(detail_header, text="Mở Facebook (O)", width=125, command=self.open_post).pack(side="right")
        self.consider_button = ctk.CTkButton(
            detail_header, text="Lưu xem xét (Y)", width=140, command=self.save_for_consideration
        )
        self.consider_button.pack(side="right", padx=6)
        self.skip_button = ctk.CTkButton(
            detail_header,
            text="Bỏ qua (D)",
            width=80,
            command=self.mark_skipped,
            fg_color="#64748b",
            hover_color="#475569",
        )
        self.skip_button.pack(side="right", padx=6)
        self.details = ctk.CTkTextbox(
            detail_panel, font=("Segoe UI", 16), wrap="word", spacing1=3, spacing3=6
        )
        self.details.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.set_text(self.details, "Chọn một bài để xem nội dung. Nhấp đúp để mở bài trên Facebook.")
        self.log = ctk.CTkTextbox(panel, height=105, font=("Consolas", 11), wrap="word")
        self.log.grid(row=5, column=0, sticky="ew")
        self.log.configure(state="disabled")
        ctk.CTkButton(
            panel,
            text="Mở thư mục dữ liệu / Excel",
            command=lambda: os.startfile(str(self.data_dir)),
            fg_color="#475569",
            hover_color="#334155",
        ).grid(row=6, column=0, sticky="w", pady=(10, 0))

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

    @staticmethod
    def evaluation_label(row):
        return {"suitable": "Phù hợp", "review": "Cần xem lại",
                "unsuitable": "Không phù hợp"}.get(row["evaluation"], "Cần xem lại")

    def filtered_rows(self):
        location = {"HCM": "hcm", "Chưa rõ địa điểm": "unknown"}.get(
            self.location_filter.get()
        )
        evaluation = {"Phù hợp": "suitable", "Cần xem lại": "review"}.get(self.evaluation_filter.get())
        processing = {
            "Chưa xử lý": "unprocessed",
            "Đã lưu xem xét": "considered",
            "Đang theo dõi": "tracked",
            "Đã bỏ qua": "skipped",
        }.get(self.processing_filter.get())
        rows = self.store.grouped_posts(self.search.get().strip(), category="all")
        return [
            row
            for row in rows
            if row["evaluation"] in {"suitable", "review"}
            and row["location"] != "outside"
            and (location is None or row["location"] == location)
            and (evaluation is None or row["evaluation"] == evaluation)
            and (processing is None or row["processing"] == processing)
        ]

    def refresh_results(self):
        visible = self.filtered_rows()
        total = len(visible)
        if self.offset >= total:
            self.offset = max(0, ((total - 1) // self.PAGE_SIZE) * self.PAGE_SIZE)
        rows = visible[self.offset : self.offset + self.PAGE_SIZE]
        selected = self.table.selection()
        self.rows = {str(row["id"]): row for row in rows}
        for item in self.table.get_children():
            self.table.delete(item)
        for key, row in self.rows.items():
            self.table.insert(
                "",
                "end",
                iid=key,
                tags=("applied",)
                if row.get("application_ids")
                else ("review",)
                if row["evaluation"] == "review"
                else (),
                values=(
                    row.get("application_status") or {
                        "considered": "Đã lưu xem xét",
                        "skipped": "Đã bỏ qua",
                    }.get(row["processing"], "Chưa xử lý"),
                    self.evaluation_label(row),
                    local_time(row["detected_at"])[:19],
                    row["group_name"],
                    ", ".join(json.loads(row["keywords"])),
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
                f"Đánh giá: {self.evaluation_label(row)} · "
                f"Theo dõi: {row.get('application_status') or {'considered': 'Đã lưu xem xét', 'skipped': 'Đã bỏ qua'}.get(row['processing'], 'Chưa xử lý')} · "
                f"{len(row.get('source_urls', [row['url']]))} bài trùng nội dung\n"
                f"{row['url']}\nNguồn: {' | '.join(row.get('source_urls', [row['url']]))}\n"
                f"Ngày đăng: {local_time(row['posted_at']) or row['posted_time_raw'] or 'Không xác định'}"
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

    def create_application_from_post(self):
        row = self.selected_row()
        if row:
            self.open_tracker(row)

    def select_row(self, iid):
        if iid in self.rows:
            self.table.selection_set(iid)
            self.table.focus(iid)
            self.table.see(iid)
            self.show_details()

    def move_post(self, direction):
        children = self.table.get_children()
        if not children:
            return
        selected = self.table.selection()
        index = children.index(selected[0]) if selected else (-1 if direction > 0 else 0)
        target = index + direction
        if 0 <= target < len(children):
            self.select_row(children[target])
            return
        total = len(self.filtered_rows())
        if direction > 0 and self.offset + self.PAGE_SIZE < total:
            self.offset += self.PAGE_SIZE
            self.refresh_results()
            self.select_row(self.table.get_children()[0])
        elif direction < 0 and self.offset:
            self.offset = max(0, self.offset - self.PAGE_SIZE)
            self.refresh_results()
            self.select_row(self.table.get_children()[-1])

    def move_after_post_action(self, previous_id, index):
        self.refresh_results()
        children = self.table.get_children()
        if not children:
            return
        if previous_id in children:
            index = min(index + 1, len(children) - 1)
        else:
            index = min(index, len(children) - 1)
        self.select_row(children[index])

    def save_for_consideration(self):
        row = self.selected_row()
        if not row or row.get("user_decision") == "considered":
            return
        children = self.table.get_children()
        index = children.index(str(row["id"]))
        self.store.set_user_decision(row["content_hash"], "considered")
        self.post_undo.append(("consider", row["content_hash"], str(row["id"])))
        self.move_after_post_action(str(row["id"]), index)

    def mark_skipped(self):
        row = self.selected_row()
        if not row:
            return
        children = self.table.get_children()
        index = children.index(str(row["id"]))
        self.store.set_user_decision(row["content_hash"], "skipped")
        self.post_undo.append(("skip", row["content_hash"], str(row["id"])))
        self.move_after_post_action(str(row["id"]), index)

    def open_tracker(self, source=None):
        from monitor.tracking_ui import TrackingPanel

        if self.tracker is None or not self.tracker.winfo_exists():
            self.tracker = TrackingPanel(self, self.store, self.refresh_results, self.show_posts)
        else:
            self.tracker.refresh()
        self.results_panel.grid_remove()
        if self.saved_panel is not None and self.saved_panel.winfo_ismapped():
            self.saved_panel.grid_remove()
        if source:
            self.tracker.new(source)
        self.tracker.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        self.tracker.focus_set()

    def open_saved_considerations(self):
        from monitor.saved_posts_ui import SavedPostsPanel

        if self.saved_panel is None or not self.saved_panel.winfo_exists():
            self.saved_panel = SavedPostsPanel(
                self, self.store, self.refresh_results, self.show_posts, self.open_tracker
            )
        else:
            self.saved_panel.refresh()
        self.results_panel.grid_remove()
        if self.tracker is not None and self.tracker.winfo_ismapped():
            self.tracker.grid_remove()
        self.saved_panel.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        self.saved_panel.focus_set()

    def show_posts(self):
        # Keep the form alive so switching views preserves unsaved edits.
        if self.tracker is not None and self.tracker.winfo_ismapped():
            self.tracker.grid_remove()
        if self.saved_panel is not None and self.saved_panel.winfo_ismapped():
            self.saved_panel.grid_remove()
        self.results_panel.grid()
        self.refresh_results()

    def editing_text(self):
        if self.checks_panel is not None and self.checks_panel.winfo_ismapped():
            return True
        widget = self.focus_get()
        return widget is not None and widget.winfo_class() in {"Entry", "Text", "TEntry", "TCombobox"}

    def handle_post_shortcut(self, event, direction):
        if not self.editing_text():
            if self.tracker is not None and self.tracker.winfo_ismapped():
                self.tracker.move_application(direction)
            elif self.saved_panel is not None and self.saved_panel.winfo_ismapped():
                self.saved_panel.move_post(direction)
            else:
                self.move_post(direction)
            return "break"
        return None

    def handle_post_action_shortcut(self, event, action):
        if not self.editing_text():
            if self.tracker is not None and self.tracker.winfo_ismapped():
                if event.keysym.lower() == "d":
                    self.tracker.delete_current()
                    return "break"
            elif self.saved_panel is not None and self.saved_panel.winfo_ismapped():
                if event.keysym.lower() == "d":
                    self.saved_panel.remove_current()
                    return "break"
            else:
                action()
                return "break"
        return None

    def handle_open_post_shortcut(self, event):
        if not self.editing_text():
            if self.saved_panel is not None and self.saved_panel.winfo_ismapped():
                self.saved_panel.open_post()
            elif self.tracker is None or not self.tracker.winfo_ismapped():
                self.open_post()
            return "break"
        return None

    def handle_ctrl_s(self, event):
        if self.tracker is not None and self.tracker.winfo_ismapped():
            self.tracker.save()
            return "break"
        return None

    def handle_ctrl_z(self, event):
        if self.editing_text():
            return None
        if self.tracker is not None and self.tracker.winfo_ismapped():
            self.tracker.undo()
        elif self.saved_panel is not None and self.saved_panel.winfo_ismapped():
            self.saved_panel.undo()
        else:
            self.undo_post_action()
        return "break"

    def undo_post_action(self):
        if not self.post_undo:
            return
        kind, value, row_id = self.post_undo.pop()
        self.store.set_user_decision(value, None)
        self.refresh_results()
        self.select_row(row_id)

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
                rows = self.filtered_rows()
                export_posts(rows, Path(filename))
                self.export_events.put(("log", f"Đã xuất {len(rows)} bài: {filename}"))
            except Exception as exc:
                self.export_events.put(("error", f"Không xuất được file: {exc}"))

        self.export_thread = Thread(target=run, name="export")
        self.export_thread.start()

    def open_checks(self):
        from monitor.checks_ui import ChecksPanel

        if self.checks_panel is None:
            self.checks_panel = ChecksPanel(self)
        self.results_panel.grid_remove()
        self.checks_panel.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        self.checks_panel.refresh()

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
                elif kind == "checks":
                    self.checks_button.configure(text=f"Kiểm tra group ({len(self.store.scan_checks())})")
                    if self.checks_panel is not None and self.checks_panel.winfo_ismapped():
                        self.checks_panel.refresh()
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
        if self.tracker is not None and self.tracker.winfo_exists():
            if not self.tracker.can_leave():
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
