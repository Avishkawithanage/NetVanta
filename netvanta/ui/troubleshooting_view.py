"""Troubleshooting workspace: a tool list on the left, the selected tool on the right."""

from __future__ import annotations

import customtkinter as ctk

from . import theme
from .context import AppContext
from .panels import PANELS


class TroubleshootingView(ctk.CTkFrame):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, fg_color="transparent")
        self.ctx = ctx
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        side = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=12, width=190)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="TOOLS", font=theme.font(11, "bold"), text_color=theme.MUTED).pack(anchor="w", padx=14, pady=(12, 4))
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.grid(row=0, column=1, sticky="nsew")
        self.holder.columnconfigure(0, weight=1)
        self.holder.rowconfigure(0, weight=1)
        self.buttons: dict[str, ctk.CTkButton] = {}
        self.panels: dict[str, ctk.CTkFrame] = {}
        self.current = ""
        for name, cls in PANELS:
            panel = cls(self.holder, ctx)
            panel.grid(row=0, column=0, sticky="nsew")
            self.panels[name] = panel
            btn = ctk.CTkButton(side, text=name, anchor="w", height=32, corner_radius=8, font=theme.font(13),
                                fg_color="transparent", text_color=theme.TEXT, hover_color=theme.SURFACE_ALT,
                                command=lambda n=name: self.show_tool(n))
            btn.pack(fill="x", padx=8, pady=1)
            self.buttons[name] = btn
        self.show_tool(PANELS[0][0])

    def show_tool(self, name: str, run: bool = False) -> None:
        if name not in self.panels:
            return
        self.current = name
        for key, panel in self.panels.items():
            if key != name:
                panel.grid_remove()  # hidden tools are not re-laid-out while the window is resized
        self.panels[name].grid()
        self.panels[name].tkraise()
        for key, btn in self.buttons.items():
            btn.configure(fg_color=theme.ACCENT if key == name else "transparent",
                          text_color="#ffffff" if key == name else theme.TEXT)
        self.panels[name].on_show()
        if run:
            self.panels[name].run()
