import customtkinter as ctk


class ChecksPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.app = master
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkButton(self, text="← Danh sách bài", command=self.back).grid(
            row=0, column=0, sticky="w", padx=12, pady=12)
        self.heading = ctk.CTkLabel(self, text="", anchor="w", wraplength=700)
        self.heading.grid(row=1, column=0, sticky="ew", padx=12)
        self.listing = ctk.CTkScrollableFrame(self)
        self.listing.grid(row=2, column=0, sticky="nsew", padx=12, pady=12)

    def back(self):
        self.grid_remove()
        self.app.results_panel.grid()

    def refresh(self):
        rows = self.app.store.scan_checks()
        self.app.checks_button.configure(text=f"Kiểm tra group ({len(rows)})")
        self.heading.configure(text=f"{len(rows)} group cần kiểm tra · Không xác nhận đã đọc hết bài.\n"
                               "Đã kiểm tra chỉ xác nhận cảnh báo hiện tại; lượt sau có thể báo lại.")
        for child in self.listing.winfo_children():
            child.destroy()
        for row in rows:
            card = ctk.CTkFrame(self.listing)
            card.pack(fill="x", pady=5)
            label = {"error": "QUÉT LỖI", "warning": "CẦN KIỂM TRA",
                     "pending": "CHƯA HOÀN TẤT"}[row["severity"]]
            count = row["read_count"] if row["read_count"] is not None else "Chưa xác định"
            ctk.CTkLabel(card, text=f"{label} · {row['group_name']}", anchor="w",
                         text_color="#dc2626" if row["severity"] == "error" else "#a16207",
                         wraplength=650).pack(fill="x", padx=10)
            ctk.CTkLabel(card, text=f"{row['checked_at']} · Đọc: {count}\n{row['group_url']}\n"
                         f"{row['reason']}", justify="left", anchor="w", wraplength=650).pack(
                             fill="x", padx=10)
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=10, pady=8)
            ctk.CTkButton(actions, text="Mở group",
                         command=lambda url=row["group_url"]: self.app.open_group(url)).pack(side="left")
            ctk.CTkButton(actions, text="Đã kiểm tra",
                         command=lambda item=row: self.resolve(item)).pack(side="left", padx=8)

    def resolve(self, row):
        self.app.store.resolve_scan_check(row["group_url"], row["revision"])
        self.refresh()
