"""Colours, fonts and shared styling. Colour tuples are (light, dark)."""

from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk

from ..models.results import Status

BG = ("#f3f5f9", "#0e1522")
SIDEBAR = ("#e4e9f2", "#0a101b")
SURFACE = ("#ffffff", "#162033")
SURFACE_ALT = ("#eaeef5", "#1d2a42")
BORDER = ("#cfd6e4", "#26344f")
TEXT = ("#0f172a", "#e8eef9")
MUTED = ("#5b6577", "#97a6c0")
ACCENT = ("#2563eb", "#3b82f6")
ACCENT_HOVER = ("#1d4ed8", "#2563eb")
DANGER = ("#dc2626", "#ef4444")
DANGER_HOVER = ("#b91c1c", "#dc2626")

STATUS_STYLE: dict[Status, tuple[str, str]] = {
    Status.PASS: ("✔ PASS", "#16a34a"),
    Status.FAIL: ("✖ FAIL", "#dc2626"),
    Status.WARNING: ("⚠ WARNING", "#d97706"),
    Status.SKIPPED: ("– SKIPPED", "#64748b"),
    Status.UNKNOWN: ("? UNKNOWN", "#64748b"),
}

FONT_FAMILY = "Segoe UI"
MONO = ("Consolas", 12)


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def apply_tree_style(root) -> None:
    """Style ttk.Treeview to match the current appearance mode."""
    dark = ctk.get_appearance_mode() == "Dark"
    bg, fg, head = ("#162033", "#e8eef9", "#1d2a42") if dark else ("#ffffff", "#0f172a", "#eaeef5")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg, rowheight=28,
                    borderwidth=0, font=(FONT_FAMILY, 10))
    style.configure("Treeview.Heading", background=head, foreground=fg, relief="flat",
                    font=(FONT_FAMILY, 10, "bold"), padding=6)
    style.map("Treeview", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])
    style.map("Treeview.Heading", background=[("active", head)])
