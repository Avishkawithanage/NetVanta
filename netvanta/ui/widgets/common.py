"""Small reusable widgets."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from ...models.results import Status
from .. import theme


class StatusChip(ctk.CTkLabel):
    def __init__(self, master, **kw):
        super().__init__(master, text="", corner_radius=12, width=96, height=26, font=theme.font(12, "bold"),
                         text_color="#ffffff", fg_color="transparent", **kw)

    def set_status(self, status: Status | None, text: str | None = None) -> None:
        if status is None:
            self.configure(text="", fg_color="transparent")
            return
        label, color = theme.STATUS_STYLE[status]
        self.configure(text=text or label, fg_color=color)

    def set_busy(self, text: str = "RUNNING…") -> None:
        self.configure(text=text, fg_color=theme.ACCENT)


def primary_button(master, text, command, width=130, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, width=width, height=34, font=theme.font(13, "bold"),
                         fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color="#ffffff", **kw)


def secondary_button(master, text, command, width=110, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, width=width, height=34, font=theme.font(13),
                         fg_color=theme.SURFACE_ALT, hover_color=theme.BORDER, text_color=theme.TEXT, **kw)


def danger_button(master, text, command, width=110, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, width=width, height=34, font=theme.font(13),
                         fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER, text_color="#ffffff", **kw)


def title_block(master, title: str, subtitle: str) -> ctk.CTkFrame:
    frame = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(frame, text=title, font=theme.font(24, "bold"), text_color=theme.TEXT, anchor="w").pack(anchor="w")
    ctk.CTkLabel(frame, text=subtitle, font=theme.font(13), text_color=theme.MUTED, anchor="w",
                 justify="left", wraplength=760).pack(anchor="w", pady=(2, 0))
    return frame


def card(master, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(master, fg_color=theme.SURFACE, corner_radius=12, border_width=1, border_color=theme.BORDER, **kw)


def output_box(master, wrap: str = "none") -> ctk.CTkTextbox:
    box = ctk.CTkTextbox(master, font=theme.MONO, fg_color=theme.SURFACE, text_color=theme.TEXT, corner_radius=10,
                         border_width=1, border_color=theme.BORDER, wrap=wrap, activate_scrollbars=True)
    box.configure(state="disabled")
    return box


def set_text(box: ctk.CTkTextbox, text: str) -> None:
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.insert("1.0", text)
    box.configure(state="disabled")


def append_text(box: ctk.CTkTextbox, text: str) -> None:
    box.configure(state="normal")
    box.insert("end", text + "\n")
    box.see("end")
    box.configure(state="disabled")


def copy_to_clipboard(root, text: str) -> bool:
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
        return True
    except tk.TclError:
        messagebox.showerror("NetVanta", "Could not access the clipboard.")
        return False
