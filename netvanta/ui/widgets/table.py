"""Sortable ttk.Treeview with a scrollbar."""

from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk


class SortableTree(ctk.CTkFrame):
    def __init__(self, master, columns: list[tuple[str, str, int]], height: int = 10, selectmode: str = "extended"):
        super().__init__(master, fg_color="transparent")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings", height=height,
                                 selectmode=selectmode)
        for key, title, width in columns:
            self.tree.heading(key, text=title, command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, anchor="w", stretch=True)
        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        self._reverse: dict[str, bool] = {}

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def insert(self, iid: str, values: tuple, tags: tuple = ()) -> None:
        self.tree.insert("", "end", iid=iid, values=values, tags=tags)

    def selected(self) -> list[str]:
        return list(self.tree.selection())

    def sort_by(self, column: str) -> None:
        reverse = not self._reverse.get(column, True)
        self._reverse = {column: reverse}
        items = [(self.tree.set(i, column), i) for i in self.tree.get_children("")]

        def key(item):
            text = item[0]
            try:
                return (0, float(text.split()[0]))
            except (ValueError, IndexError):
                return (1, text.lower())

        items.sort(key=key, reverse=reverse)
        for index, (_value, iid) in enumerate(items):
            self.tree.move(iid, "", index)
