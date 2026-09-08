import tkinter as tk


class LinkTooltip:
    """A passive URL hint that never takes keyboard focus."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.popup = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")
        widget.bind("<MouseWheel>", self.hide, add="+")

    def show(self, event):
        self.hide()
        popup = self.popup = tk.Toplevel(self.widget)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        tk.Label(popup, text=self.text, background="#fff8d6", foreground="#172033",
                 relief="solid", borderwidth=1, padx=8, pady=5,
                 wraplength=500, justify="left").pack()
        popup.update_idletasks()
        x = max(0, min(event.x_root + 12, popup.winfo_screenwidth() - popup.winfo_reqwidth()))
        y = max(0, min(event.y_root + 24, popup.winfo_screenheight() - popup.winfo_reqheight()))
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()

    def hide(self, event=None):
        if self.popup is not None:
            self.popup.destroy()
            self.popup = None
