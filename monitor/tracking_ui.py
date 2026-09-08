import sqlite3
from tkinter import messagebox, ttk

import customtkinter as ctk

from monitor.core import normalize
from monitor.tracking import FIELDS, STATUSES


class TrackingPanel(ctk.CTkFrame):
    """Application tracking stays in the main window and keeps draft form data while hidden."""

    def __init__(self, parent, store, on_change, on_back):
        super().__init__(parent)
        self.store = store
        self.on_change = on_change
        self.on_back = on_back
        self.current_id = None
        self.loading = False
        self.undo_stack = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(header, text="← Danh sách bài", width=135, command=on_back).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(header, text="Theo dõi ứng tuyển", font=("Segoe UI", 22, "bold")).grid(row=0, column=1)
        ctk.CTkButton(header, text="+ Hồ sơ mới", width=125, command=self.new).grid(
            row=0, column=2, sticky="e"
        )

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        filters.grid_columnconfigure(0, weight=1)
        self.search = ctk.CTkEntry(filters, placeholder_text="Tìm công ty, vị trí, liên hệ, ghi chú…")
        self.search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.search.bind("<KeyRelease>", lambda _: self.refresh())
        self.status_filter = ctk.CTkOptionMenu(
            filters, values=["Tất cả", *STATUSES], command=lambda _: self.refresh(), width=155
        )
        self.status_filter.grid(row=0, column=1)

        left = ctk.CTkFrame(self)
        left.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)
        self.table = ttk.Treeview(
            left,
            columns=("company", "position", "status", "interview_at", "delete"),
            show="headings",
            selectmode="browse",
        )
        for key, label, width in (
            ("company", "Công ty", 155),
            ("position", "Vị trí", 155),
            ("status", "Trạng thái", 135),
            ("interview_at", "Lịch phỏng vấn", 145),
            ("delete", "", 58),
        ):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=45, anchor="center" if key == "delete" else "w")
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(left, command=self.table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(left, orient="horizontal", command=self.table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.bind("<<TreeviewSelect>>", self.select)
        self.table.bind("<ButtonRelease-1>", self.table_click)
        self.count = ctk.CTkLabel(left, text="")
        self.count.grid(row=2, column=0, sticky="w", padx=8, pady=(4, 0))

        form = ctk.CTkFrame(self)
        form.grid(row=1, column=1, rowspan=2, padx=(0, 12), pady=(0, 12), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)
        form.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(form, text="Thông tin hồ sơ", font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, padx=12, pady=(10, 4), sticky="w"
        )
        body = ctk.CTkScrollableFrame(form)
        body.grid(row=1, column=0, padx=8, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        self.fields = {}
        for index, (key, label) in enumerate(FIELDS.items()):
            ctk.CTkLabel(body, text=label, anchor="w").grid(row=index * 2, column=0, sticky="ew")
            entry = ctk.CTkEntry(body)
            entry.grid(row=index * 2 + 1, column=0, sticky="ew", pady=(0, 5))
            entry.bind("<KeyRelease>", self.changed)
            self.fields[key] = entry
        row = len(FIELDS) * 2
        ctk.CTkLabel(body, text="Trạng thái", anchor="w").grid(row=row, column=0, sticky="ew")
        self.status = ctk.CTkOptionMenu(body, values=STATUSES, command=self.changed)
        self.status.grid(row=row + 1, column=0, sticky="ew")
        ctk.CTkLabel(body, text="Ghi chú / lịch sử các vòng phỏng vấn", anchor="w").grid(
            row=row + 2, column=0, sticky="ew"
        )
        self.notes = ctk.CTkTextbox(body, height=150, wrap="word")
        self.notes.grid(row=row + 3, column=0, sticky="ew", pady=(0, 8))
        self.notes.bind("<KeyRelease>", self.changed)
        footer = ctk.CTkFrame(form, fg_color="transparent")
        footer.grid(row=2, column=0, padx=12, pady=10, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self.notice = ctk.CTkLabel(footer, text="")
        self.notice.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(footer, text="Lưu hồ sơ  Ctrl+S", width=155, command=self.save).grid(
            row=0, column=1, sticky="e"
        )
        self.refresh()
        self.new(force=True)

    def changed(self, _event=None):
        if not self.loading:
            self.notice.configure(text="Chưa lưu thay đổi")

    def form_value(self):
        value = {key: widget.get() for key, widget in self.fields.items()}
        value.update(status=self.status.get(), notes=self.notes.get("1.0", "end-1c"))
        return value

    def can_leave(self):
        return self.form_value() == self.saved_value or messagebox.askyesno(
            "Thay đổi chưa lưu", "Bỏ các thay đổi chưa lưu của hồ sơ đang nhập?", parent=self
        )

    def fill(self, value):
        self.loading = True
        for key, widget in self.fields.items():
            widget.delete(0, "end")
            widget.insert(0, value.get(key, ""))
        self.status.set(value.get("status", STATUSES[0]))
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", value.get("notes", ""))
        self.current_id = value.get("id")
        self.loading = False
        self.saved_value = self.form_value()
        self.notice.configure(text="Hồ sơ mới" if self.current_id is None else "Đã tải hồ sơ")

    def new(self, source=None, force=False):
        if not force and not self.can_leave():
            return
        self.table.selection_remove(*self.table.selection())
        value = {"status": "Đang xem xét"}
        if source:
            value.update(source_url=source["url"], notes=source["content"])
        self.fill(value)
        if source:
            self.saved_value = {**self.saved_value, "source_url": "", "notes": ""}
            self.changed()
        self.fields["company"].focus_set()

    def refresh(self):
        self.rows = {str(row["id"]): row for row in self.store.applications()}
        search = normalize(self.search.get())
        status = self.status_filter.get()
        self.table.delete(*self.table.get_children())
        for key, row in self.rows.items():
            if status != "Tất cả" and row["status"] != status:
                continue
            if search and search not in normalize(" ".join(str(value) for value in row.values())):
                continue
            self.table.insert(
                "",
                "end",
                iid=key,
                values=(*[row[field] for field in ("company", "position", "status", "interview_at")], "Xóa"),
            )
        self.count.configure(text=f"{len(self.table.get_children())} hồ sơ · Q/E chuyển · D xóa")

    def select(self, _event=None):
        selected = self.table.selection()
        if not selected or selected[0] == str(self.current_id):
            return
        if self.can_leave():
            self.fill(self.rows[selected[0]])
        else:
            self.table.selection_remove(*selected)
            if self.current_id and self.table.exists(str(self.current_id)):
                self.table.selection_set(str(self.current_id))

    def table_click(self, event):
        if self.table.identify_column(event.x) != "#5":
            return
        identity = self.table.identify_row(event.y)
        if identity:
            self.delete(identity)

    def open_application(self, identity):
        if identity != self.current_id and self.can_leave():
            self.refresh()
            if str(identity) in self.rows:
                self.fill(self.rows[str(identity)])

    def move_application(self, direction):
        rows = self.table.get_children()
        if not rows:
            return
        selected = self.table.selection()
        index = rows.index(selected[0]) if selected else (-1 if direction > 0 else 0)
        target = index + direction
        if 0 <= target < len(rows):
            self.table.selection_set(rows[target])
            self.table.focus(rows[target])
            self.table.see(rows[target])
            self.select()

    def save(self):
        value = self.form_value()
        previous = self.rows.get(str(self.current_id)) if self.current_id else None
        try:
            self.current_id = self.store.save_application(value, self.current_id)
        except (ValueError, sqlite3.Error) as exc:
            messagebox.showerror("Không lưu được hồ sơ", str(exc), parent=self)
            return
        self.undo_stack.append(("update", previous) if previous else ("create", self.current_id))
        self.saved_value = self.form_value()
        self.refresh()
        self.table.selection_set(str(self.current_id))
        self.notice.configure(text="Đã lưu hồ sơ")
        self.on_change()

    def delete_current(self):
        self.delete(self.current_id)

    def delete(self, identity=None):
        identity = identity or self.current_id
        if identity is None:
            return
        if not self.can_leave():
            return
        row = self.rows.get(str(identity))
        if row is None:
            return
        name = " · ".join(value for value in (row["company"], row["position"]) if value) or "hồ sơ này"
        if not messagebox.askyesno("Xóa hồ sơ", f"Xóa {name}?", parent=self):
            return
        try:
            self.store.delete_application(identity)
        except sqlite3.Error as exc:
            messagebox.showerror("Không xóa được hồ sơ", str(exc), parent=self)
            return
        self.undo_stack.append(("delete", row))
        self.refresh()
        self.new(force=True)
        self.on_change()

    def undo(self):
        if not self.undo_stack:
            return
        kind, value = self.undo_stack.pop()
        if kind == "create":
            self.store.delete_application(value)
            self.current_id = None
        elif kind == "delete":
            self.store.restore_application(value)
            self.current_id = value["id"]
        else:
            self.store.save_application(value, value["id"])
            self.current_id = value["id"]
        self.refresh()
        if self.current_id is not None and self.table.exists(str(self.current_id)):
            self.table.selection_set(str(self.current_id))
            self.fill(self.rows[str(self.current_id)])
        self.notice.configure(text="Đã hoàn tác")
        self.on_change()
