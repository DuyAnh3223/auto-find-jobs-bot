import json
import webbrowser
from tkinter import ttk

import customtkinter as ctk

from monitor.exporter import local_time


class SavedPostsPanel(ctk.CTkFrame):
    """Posts intentionally saved for later review, separate from applications."""

    def __init__(self, parent, store, on_change, on_back, on_track):
        super().__init__(parent)
        self.store = store
        self.on_change = on_change
        self.on_back = on_back
        self.on_track = on_track
        self.rows = {}
        self.undo_stack = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(header, text="← Danh sách bài", width=135, command=on_back).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(header, text="Bài lưu xem xét", font=("Segoe UI", 22, "bold")).grid(
            row=0, column=1
        )
        self.count = ctk.CTkLabel(header, text="")
        self.count.grid(row=0, column=2, sticky="e")

        left = ctk.CTkFrame(self)
        left.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        self.search = ctk.CTkEntry(left, placeholder_text="Tìm nội dung, group, từ khóa…")
        self.search.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        self.search.bind("<KeyRelease>", lambda _: self.refresh())
        self.table = ttk.Treeview(
            left, columns=("time", "group", "keywords"), show="headings", selectmode="browse"
        )
        for key, label, width in (
            ("time", "Ngày lưu", 145),
            ("group", "Group", 150),
            ("keywords", "Từ khóa", 170),
        ):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=80)
        self.table.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        vertical = ttk.Scrollbar(left, command=self.table.yview)
        vertical.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        self.table.configure(yscrollcommand=vertical.set)
        self.table.bind("<<TreeviewSelect>>", self.show_details)
        self.table.bind("<Double-1>", self.open_post)

        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, padx=(0, 12), pady=(0, 12), sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=0, column=0, padx=12, pady=10, sticky="ew")
        ctk.CTkLabel(actions, text="Nội dung bài đăng", font=("Segoe UI", 17, "bold")).pack(side="left")
        ctk.CTkButton(actions, text="Mở Facebook (O)", width=125, command=self.open_post).pack(side="right")
        ctk.CTkButton(
            actions, text="+ Theo dõi ứng tuyển", width=155, command=self.create_application
        ).pack(side="right", padx=6)
        ctk.CTkButton(
            actions, text="Bỏ lưu (D)", width=100, command=self.remove_current,
            fg_color="#64748b", hover_color="#475569",
        ).pack(side="right", padx=6)
        self.details = ctk.CTkTextbox(right, font=("Segoe UI", 15), wrap="word", spacing1=3, spacing3=6)
        self.details.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.set_text("Chọn một bài đã lưu để xem nội dung.")

    def set_text(self, text):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def refresh(self):
        selected = self.table.selection()
        self.rows = {
            str(row["id"]): row for row in self.store.saved_considerations(self.search.get().strip())
        }
        self.table.delete(*self.table.get_children())
        for key, row in self.rows.items():
            self.table.insert(
                "", "end", iid=key,
                values=(local_time(row["detected_at"])[:19], row["group_name"], ", ".join(json.loads(row["keywords"]))),
            )
        self.count.configure(text=f"{len(self.rows)} bài lưu xem xét · Q/E chuyển · D bỏ lưu")
        if selected and selected[0] in self.rows:
            self.table.selection_set(selected[0])
            self.show_details()
        elif self.rows:
            first = next(iter(self.rows))
            self.table.selection_set(first)
            self.show_details()
        else:
            self.set_text("Chưa có bài nào được lưu xem xét.")

    def selected_row(self):
        selected = self.table.selection()
        return self.rows.get(selected[0]) if selected else None

    def show_details(self, _event=None):
        row = self.selected_row()
        if not row:
            return
        tracking = row.get("application_status")
        self.set_text(
            f"{row['group_name']} · {', '.join(json.loads(row['keywords']))}\n"
            f"Đã lưu xem xét · {len(row.get('source_urls', [row['url']]))} bài trùng nội dung\n"
            + (f"Đã có hồ sơ theo dõi: {tracking}\n" if tracking else "")
            + f"{row['url']}\nNguồn: {' | '.join(row.get('source_urls', [row['url']]))}\n"
            f"Ngày đăng: {local_time(row['posted_at']) or row['posted_time_raw'] or 'Không xác định'}\n"
            f"Phát hiện: {local_time(row['detected_at'])}\n\n{row['content']}"
        )

    def open_post(self, _event=None):
        if _event is not None:
            item = self.table.identify_row(_event.y)
            if not item:
                return
            self.table.selection_set(item)
        row = self.selected_row()
        if row:
            webbrowser.open(row["url"])

    def move_post(self, direction):
        items = self.table.get_children()
        if not items:
            return
        selected = self.table.selection()
        index = items.index(selected[0]) if selected else (-1 if direction > 0 else 0)
        target = index + direction
        if 0 <= target < len(items):
            self.table.selection_set(items[target])
            self.table.focus(items[target])
            self.table.see(items[target])
            self.show_details()

    def remove_current(self):
        row = self.selected_row()
        if not row:
            return
        self.store.set_user_decision(row["content_hash"], None)
        self.undo_stack.append(row["content_hash"])
        self.refresh()
        self.on_change()

    def create_application(self):
        row = self.selected_row()
        if row:
            self.on_track(row)

    def undo(self):
        if not self.undo_stack:
            return
        self.store.set_user_decision(self.undo_stack.pop(), "considered")
        self.refresh()
        self.on_change()
