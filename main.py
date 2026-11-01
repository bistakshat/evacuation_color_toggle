"""Tkinter GUI for the Emergency Evacuation Planning System.

Run with: python main.py
Only Python's standard library (Tkinter) is required.
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, List, Optional, Tuple

from evacuation_engine import EvacuationGroup, EvacuationModel, RouteResult


class EvacuationApp(tk.Tk):
    # Light, high-contrast palette.  The route colours are intentionally
    # strong enough to remain visible on the white map and are repeated in
    # the route legend and the instructions panel.
    BG = "#ffffff"
    PANEL = "#ffffff"
    PANEL_2 = "#f5f7fb"
    BORDER = "#d6deea"
    TEXT = "#1f2937"
    MUTED = "#52647d"
    TEAL = "#0f766e"
    ORANGE = "#b45309"
    RED = "#be123c"
    ROUTE_COLOR_NAMES = {
        "#2563eb": "Blue",
        "#b45309": "Amber",
        "#be123c": "Rose",
        "#7c3aed": "Purple",
        "#047857": "Green",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Emergency Evacuation Planning System")
        self.geometry("1440x850")
        self.minsize(1180, 720)
        self.configure(bg=self.BG)

        self.model = EvacuationModel()
        self.scenario_var = tk.StringVar(value=self.model.SCENARIOS[0])
        self.algorithm_var = tk.StringVar(value="A* — crowd-aware")
        self.selected_node: Optional[str] = None
        self.selected_edge_key: Optional[Tuple[str, str]] = None
        self.selected_group_id = self.model.groups[0].group_id
        self.routes: Dict[str, RouteResult] = {}
        # Controls only the visibility of colored group-route overlays.
        # It does not change route calculations or any AI algorithm.
        self.show_group_route_colors = True
        self.node_loads: Dict[str, float] = {}
        self.edge_loads: Dict[Tuple[str, str], float] = {}
        self.scenario_step = 0
        self.status_var = tk.StringVar(value="Ready to plan")
        self._last_canvas_size: Optional[Tuple[int, int]] = None
        self.selected_var = tk.StringVar(value="Click an area on the map")
        self.summary_var = tk.StringVar(value="")
        self.group_location_var = tk.StringVar()
        self.group_people_var = tk.IntVar(value=8)
        self.group_access_var = tk.BooleanVar(value=False)
        self.group_choice_var = tk.StringVar()
        self.weight_vars = {
            "distance": tk.DoubleVar(value=1.0),
            "safety": tk.DoubleVar(value=2.6),
            "crowd": tk.DoubleVar(value=1.8),
            "accessibility": tk.DoubleVar(value=2.0),
        }

        self._setup_styles()
        self._build_layout()
        self._sync_group_editor()
        self.refresh()

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("Card.TFrame", background=self.PANEL_2)
        style.configure("App.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=self.PANEL, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.PANEL, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=self.PANEL, foreground=self.TEAL, font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", background=self.PANEL, foreground=self.TEAL, font=("Segoe UI", 10, "bold"))
        style.configure("TButton", background=self.PANEL_2, foreground=self.TEXT, padding=(9, 6), borderwidth=1)
        style.map("TButton", background=[("active", "#e3ebf7"), ("pressed", "#d5e1f2")])
        style.configure("Accent.TButton", background="#0f766e", foreground="#ffffff", padding=(10, 7), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#0d9488"), ("pressed", "#115e59")])
        style.configure("Danger.TButton", background="#be123c", foreground="#ffffff", padding=(9, 6), borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#9f1239")])
        style.configure(
            "TCombobox",
            fieldbackground=self.PANEL_2,
            background=self.PANEL_2,
            foreground=self.TEXT,
            selectbackground="#dbeafe",
            selectforeground=self.TEXT,
        )
        style.configure("TSpinbox", fieldbackground=self.PANEL_2, background=self.PANEL_2, foreground=self.TEXT)
        style.configure("Horizontal.TScale", background=self.PANEL)
        style.configure("TCheckbutton", background=self.PANEL, foreground=self.TEXT)
        style.configure("Treeview", background=self.PANEL_2, fieldbackground=self.PANEL_2, foreground=self.TEXT, rowheight=24)
        style.map("Treeview", background=[("selected", "#bfdbfe")], foreground=[("selected", self.TEXT)])

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        header = ttk.Frame(self, style="App.TFrame", padding=(24, 18, 24, 14))
        header.grid(row=0, column=0, columnspan=3, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ttk.Label(header, text="Emergency Evacuation", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="BFS • crowd-aware A* • utility agent • changing hazards • accessible group routing",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(20, 14)
        )
        ttk.Button(header, text="Simulate next hazard", style="Accent.TButton", command=self.next_scenario).grid(
            row=0, column=2, rowspan=2, sticky="e"
        )

        # The controls are placed inside a scrollable sidebar so they remain
        # reachable on ordinary laptop screens and at smaller window sizes.
        self.sidebar_container = ttk.Frame(self, style="Panel.TFrame")
        self.sidebar_container.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 16))
        self.sidebar_container.grid_rowconfigure(0, weight=1)
        self.sidebar_container.grid_columnconfigure(0, weight=1)
        self.sidebar_canvas = tk.Canvas(
            self.sidebar_container, background=self.PANEL, highlightthickness=0, width=300
        )
        self.sidebar_scrollbar = ttk.Scrollbar(
            self.sidebar_container, orient="vertical", command=self.sidebar_canvas.yview
        )
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)
        self.sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        self.sidebar_scrollbar.grid(row=0, column=1, sticky="ns")
        self.sidebar = ttk.Frame(self.sidebar_canvas, style="Panel.TFrame", padding=16)
        self._sidebar_window = self.sidebar_canvas.create_window(
            (0, 0), window=self.sidebar, anchor="nw"
        )
        self.sidebar.bind(
            "<Configure>",
            lambda _event: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all")),
        )
        self.sidebar_canvas.bind(
            "<Configure>",
            lambda event: self.sidebar_canvas.itemconfigure(self._sidebar_window, width=event.width),
        )
        self.sidebar_canvas.bind(
            "<MouseWheel>",
            lambda event: self.sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"),
        )
        self.sidebar.bind(
            "<MouseWheel>",
            lambda event: self.sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"),
        )
        self.sidebar.grid_columnconfigure(0, weight=1)
        self._build_sidebar()

        map_panel = ttk.Frame(self, style="Panel.TFrame", padding=14)
        map_panel.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 16))
        map_panel.grid_rowconfigure(1, weight=1)
        map_panel.grid_columnconfigure(0, weight=1)
        ttk.Label(map_panel, text="Live campus graph", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.canvas = tk.Canvas(
            map_panel,
            background="#ffffff",
            highlightthickness=1,
            highlightbackground=self.BORDER,
            relief="flat",
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Configure>", self._on_graph_canvas_resize)
        footer = ttk.Frame(map_panel, style="Panel.TFrame", padding=(2, 8, 2, 0))
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.selected_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(footer, text="Click a node to select it, or click a connection line to block/reopen it", style="Muted.TLabel").grid(
            row=0, column=1, sticky="e", padx=(8, 8)
        )
        self.route_colors_button = ttk.Button(
            footer, text="Hide route colors", command=self.toggle_group_route_colors
        )
        self.route_colors_button.grid(row=0, column=2, sticky="e")

        right_panel = ttk.Frame(self, style="Panel.TFrame", padding=14)
        right_panel.grid(row=1, column=2, sticky="nsew", padx=(8, 16), pady=(0, 16))
        right_panel.grid_rowconfigure(3, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        ttk.Label(right_panel, text="Evacuation routes", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(right_panel, textvariable=self.summary_var, style="Muted.TLabel", wraplength=340).grid(
            row=1, column=0, sticky="w", pady=(5, 10)
        )
        ttk.Label(right_panel, text="Route colours", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.legend_frame = ttk.Frame(right_panel, style="Panel.TFrame")
        self.legend_frame.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        self.legend_frame.grid_columnconfigure(0, weight=1)
        self.legend_frame.grid_columnconfigure(1, weight=1)
        route_frame = ttk.Frame(right_panel, style="Card.TFrame")
        route_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        route_frame.grid_rowconfigure(0, weight=1)
        route_frame.grid_columnconfigure(0, weight=1)
        self.route_text = tk.Text(
            route_frame,
            width=39,
            wrap="word",
            background="#fbfcfe",
            foreground=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            padx=12,
            pady=10,
            font=("Segoe UI", 9),
        )
        self.route_text.grid(row=0, column=0, sticky="nsew")
        route_scroll = ttk.Scrollbar(route_frame, orient="vertical", command=self.route_text.yview)
        route_scroll.grid(row=0, column=1, sticky="ns")
        self.route_text.configure(yscrollcommand=route_scroll.set)
        self.route_text.tag_configure("route_title", foreground=self.TEXT, font=("Segoe UI", 11, "bold"))
        self.route_text.tag_configure("route_meta", foreground=self.TEAL, font=("Segoe UI", 9, "bold"))
        self.route_text.tag_configure("warning", foreground=self.ORANGE, font=("Segoe UI", 9, "bold"))
        self.route_text.tag_configure("muted", foreground=self.MUTED)
        self.route_text.tag_configure("instruction", foreground=self.TEXT, lmargin1=10, lmargin2=10)

    def _build_sidebar(self) -> None:
        row = 0
        ttk.Label(self.sidebar, text="Route planner", style="Section.TLabel").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Label(self.sidebar, text="Algorithm", style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=(12, 3))
        row += 1
        algorithm_box = ttk.Combobox(
            self.sidebar,
            textvariable=self.algorithm_var,
            values=["BFS — nearest exit", "A* — crowd-aware", "Utility agent — balanced"],
            state="readonly",
        )
        algorithm_box.grid(row=row, column=0, sticky="ew")
        algorithm_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        row += 1
        ttk.Label(self.sidebar, text="Hazard scenario", style="Muted.TLabel").grid(row=row, column=0, sticky="w", pady=(12, 3))
        row += 1
        scenario_box = ttk.Combobox(
            self.sidebar,
            textvariable=self.scenario_var,
            values=self.model.SCENARIOS,
            state="readonly",
        )
        scenario_box.grid(row=row, column=0, sticky="ew")
        scenario_box.bind("<<ComboboxSelected>>", lambda _event: self.apply_scenario())
        row += 1
        buttons = ttk.Frame(self.sidebar, style="Panel.TFrame")
        buttons.grid(row=row, column=0, sticky="ew", pady=(7, 0))
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Apply", command=self.apply_scenario).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Reset hazards", command=self.reset_hazards).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        row += 1

        divider = ttk.Separator(self.sidebar, orient="horizontal")
        divider.grid(row=row, column=0, sticky="ew", pady=15)
        row += 1
        ttk.Label(self.sidebar, text="Utility weights", style="Section.TLabel").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Label(
            self.sidebar,
            text="Higher values make a factor more expensive in A* and more important to the utility agent.",
            style="Muted.TLabel",
            wraplength=250,
        ).grid(row=row, column=0, sticky="w", pady=(4, 7))
        row += 1
        for key, label in (
            ("distance", "Distance"),
            ("safety", "Safety penalty"),
            ("crowd", "Crowd density"),
            ("accessibility", "Accessibility"),
        ):
            weight_row = ttk.Frame(self.sidebar, style="Panel.TFrame")
            weight_row.grid(row=row, column=0, sticky="ew", pady=2)
            weight_row.grid_columnconfigure(0, weight=1)
            ttk.Label(weight_row, text=label, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
            value_label = ttk.Label(weight_row, textvariable=self._weight_display_var(key), style="Muted.TLabel")
            value_label.grid(row=0, column=1, sticky="e")
            ttk.Scale(
                weight_row,
                from_=0.0,
                to=5.0,
                variable=self.weight_vars[key],
                command=lambda _value: self.refresh(),
            ).grid(row=1, column=0, columnspan=2, sticky="ew")
            row += 1

        divider = ttk.Separator(self.sidebar, orient="horizontal")
        divider.grid(row=row, column=0, sticky="ew", pady=15)
        row += 1
        ttk.Label(self.sidebar, text="Evacuation groups", style="Section.TLabel").grid(row=row, column=0, sticky="w")
        row += 1
        group_values = [group.name for group in self.model.groups]
        self.group_choice = ttk.Combobox(self.sidebar, textvariable=self.group_choice_var, values=group_values, state="readonly")
        self.group_choice.grid(row=row, column=0, sticky="ew", pady=(6, 0))
        self.group_choice.bind("<<ComboboxSelected>>", lambda _event: self._sync_group_editor())
        row += 1
        editor = ttk.Frame(self.sidebar, style="Panel.TFrame")
        editor.grid(row=row, column=0, sticky="ew", pady=(6, 0))
        editor.grid_columnconfigure(0, weight=1)
        ttk.Label(editor, text="Starting location", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.group_location = ttk.Combobox(editor, textvariable=self.group_location_var, state="readonly")
        self.group_location.grid(row=1, column=0, sticky="ew", pady=(2, 5))
        ttk.Label(editor, text="People", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(editor, from_=1, to=500, textvariable=self.group_people_var, width=8).grid(row=3, column=0, sticky="w", pady=(2, 5))
        ttk.Checkbutton(editor, text="Requires accessible route", variable=self.group_access_var).grid(row=4, column=0, sticky="w", pady=(0, 5))
        ttk.Button(editor, text="Update selected group", command=self.update_group).grid(row=5, column=0, sticky="ew")
        row += 1
        group_buttons = ttk.Frame(self.sidebar, style="Panel.TFrame")
        group_buttons.grid(row=row, column=0, sticky="ew", pady=(6, 0))
        group_buttons.grid_columnconfigure(0, weight=1)
        group_buttons.grid_columnconfigure(1, weight=1)
        ttk.Button(group_buttons, text="Add group", command=self.add_group).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(group_buttons, text="Remove", style="Danger.TButton", command=self.remove_group).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        row += 1

        divider = ttk.Separator(self.sidebar, orient="horizontal")
        divider.grid(row=row, column=0, sticky="ew", pady=15)
        row += 1
        ttk.Label(self.sidebar, text="Selected area", style="Section.TLabel").grid(row=row, column=0, sticky="w")
        row += 1
        ttk.Label(self.sidebar, textvariable=self.selected_var, style="Muted.TLabel", wraplength=250).grid(row=row, column=0, sticky="w", pady=(4, 7))
        row += 1
        area_buttons = ttk.Frame(self.sidebar, style="Panel.TFrame")
        area_buttons.grid(row=row, column=0, sticky="ew")
        area_buttons.grid_columnconfigure(0, weight=1)
        area_buttons.grid_columnconfigure(1, weight=1)
        ttk.Button(area_buttons, text="Toggle blocked", command=self.toggle_selected_blocked).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(area_buttons, text="Toggle hazard", command=self.toggle_selected_hazard).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Button(area_buttons, text="Toggle selected connection (select a line on the map)", command=self.toggle_selected_edge_blocked).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0)
        )
        row += 1
        ttk.Label(
            self.sidebar,
            text="BFS avoids marked hazards and minimizes connections. Severe hazards (70%+) are impassable to all algorithms; A* and the utility agent score lower-level risk, crowding, distance, and accessibility.",
            style="Muted.TLabel",
            wraplength=250,
        ).grid(row=row, column=0, sticky="w", pady=(16, 0))

    def _weight_display_var(self, key: str) -> tk.StringVar:
        var = tk.StringVar()

        def update(*_args: object) -> None:
            var.set(f"{self.weight_vars[key].get():.1f}")

        self.weight_vars[key].trace_add("write", update)
        update()
        return var

    def _sync_group_editor(self) -> None:
        if not self.model.groups:
            self.group_choice_var.set("")
            return
        selected_name = self.group_choice_var.get()
        selected = next((g for g in self.model.groups if g.name == selected_name), None)
        if selected is None:
            selected = next((g for g in self.model.groups if g.group_id == self.selected_group_id), self.model.groups[0])
        self.selected_group_id = selected.group_id
        self.group_choice_var.set(selected.name)
        self.group_location_var.set(f"{selected.location} — {self.model.nodes[selected.location].name}")
        self.group_people_var.set(selected.people)
        self.group_access_var.set(selected.needs_accessible)
        if hasattr(self, "group_location"):
            self.group_location["values"] = [f"{node.node_id} — {node.name}" for node in self.model.nodes.values()]

    def _selected_group(self) -> Optional[EvacuationGroup]:
        return next((group for group in self.model.groups if group.group_id == self.selected_group_id), None)

    def update_group(self) -> None:
        group = self._selected_group()
        if group is None:
            return
        location_id = self.group_location_var.get().split(" — ", 1)[0]
        if location_id not in self.model.nodes:
            messagebox.showwarning("Invalid location", "Select a valid graph location.")
            return
        if self.model.nodes[location_id].kind in {"exit", "restricted"}:
            messagebox.showwarning(
                "Invalid starting location",
                "Choose a room or corridor. Evacuation groups should not start at an exit or in the restricted Maintenance Zone.",
            )
            return
        try:
            people = max(1, int(self.group_people_var.get()))
        except (TypeError, ValueError, tk.TclError):
            messagebox.showwarning("Invalid group size", "People must be a positive whole number.")
            return
        group.location = location_id
        group.people = people
        group.needs_accessible = bool(self.group_access_var.get())
        self.status_var.set(f"Updated {group.name}")
        self.refresh()

    def add_group(self) -> None:
        index = len(self.model.groups) + 1
        name = simpledialog.askstring("Add evacuation group", "Group name:", initialvalue=f"Group {index}", parent=self)
        if not name:
            return
        people = simpledialog.askinteger("Add evacuation group", "Number of people:", initialvalue=10, minvalue=1, maxvalue=500, parent=self)
        if people is None:
            return
        used_ids = {group.group_id for group in self.model.groups}
        next_number = 1
        while f"g{next_number}" in used_ids:
            next_number += 1
        new_group = EvacuationGroup(f"g{next_number}", name.strip(), "MAIN_HALL", people, False, "#047857")
        self.model.groups.append(new_group)
        self.group_choice["values"] = [group.name for group in self.model.groups]
        self.selected_group_id = new_group.group_id
        self.group_choice_var.set(new_group.name)
        self._sync_group_editor()
        self.refresh()

    def remove_group(self) -> None:
        if len(self.model.groups) <= 1:
            messagebox.showinfo("Keep one group", "At least one evacuation group is required.")
            return
        group = self._selected_group()
        if group is None:
            return
        self.model.groups.remove(group)
        self.selected_group_id = self.model.groups[0].group_id
        self.group_choice["values"] = [item.name for item in self.model.groups]
        self.group_choice_var.set(self.model.groups[0].name)
        self._sync_group_editor()
        self.refresh()

    def weights(self) -> Dict[str, float]:
        return {key: max(0.0, value.get()) for key, value in self.weight_vars.items()}

    def apply_scenario(self) -> None:
        self.model.apply_scenario(self.scenario_var.get())
        self.scenario_step = self.model.SCENARIOS.index(self.scenario_var.get())
        self.status_var.set(f"Scenario active: {self.scenario_var.get()}")
        self.refresh()

    def next_scenario(self) -> None:
        self.scenario_step = (self.scenario_step + 1) % len(self.model.SCENARIOS)
        self.scenario_var.set(self.model.SCENARIOS[self.scenario_step])
        self.apply_scenario()

    def reset_hazards(self) -> None:
        self.scenario_step = 0
        self.scenario_var.set(self.model.SCENARIOS[0])
        self.model.apply_scenario(self.model.SCENARIOS[0])
        self.status_var.set("Dynamic hazards reset; restricted Maintenance Zone remains blocked")
        self.refresh()

    def toggle_selected_blocked(self) -> None:
        if not self.selected_node:
            messagebox.showinfo("Select an area", "Click a room, corridor, or exit on the map first.")
            return
        node = self.model.nodes[self.selected_node]
        if node.kind == "restricted":
            messagebox.showinfo(
                "Restricted area",
                "The Maintenance Zone is permanently restricted in this demo map. Use other corridors for evacuation.",
            )
            return
        node.blocked = not node.blocked
        status = "blocked" if node.blocked else "open"
        self.selected_var.set(f"{node.node_id} · {node.name} · {status.upper()}")
        self.status_var.set(f"{node.name} is now {status}")
        self.refresh()

    def toggle_selected_hazard(self) -> None:
        if not self.selected_node:
            messagebox.showinfo("Select an area", "Click a room, corridor, or exit on the map first.")
            return
        node = self.model.nodes[self.selected_node]
        node.hazard = 0.85 if node.hazard < 0.2 else 0.0
        state = f"HAZARD {node.hazard:.0%}" if node.hazard else "OPEN"
        self.selected_var.set(f"{node.node_id} · {node.name} · {state}")
        self.status_var.set(f"Hazard level changed for {node.name}")
        self.refresh()

    @staticmethod
    def _distance_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx, dy = x2 - x1, y2 - y1
        denom = dx * dx + dy * dy
        if denom <= 1e-9:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
        projection_x, projection_y = x1 + t * dx, y1 + t * dy
        return math.hypot(px - projection_x, py - projection_y)

    def on_canvas_click(self, event: tk.Event) -> None:
        closest: Optional[str] = None
        closest_distance = float("inf")
        for node in self.model.nodes.values():
            point_x, point_y, scale = self._map_point(node)
            distance = math.hypot(event.x - point_x, event.y - point_y)
            if distance < 34 * scale and distance < closest_distance:
                closest = node.node_id
                closest_distance = distance

        if closest is not None:
            self.selected_node = closest
            self.selected_edge_key = None
            node = self.model.nodes[closest]
            if node.blocked:
                state = "BLOCKED"
            elif node.kind == "exit" and not node.is_open:
                state = "CLOSED"
            elif node.hazard > 0:
                state = f"HAZARD {node.hazard:.0%}"
            else:
                state = "OPEN"
            access = "accessible" if node.accessible else "not accessible"
            self.selected_var.set(f"{node.node_id} · {node.name} · {state} · {access}")
            self.status_var.set(f"Selected {node.name}")
            self.draw_map()
            return

        nearest_edge: Optional[Tuple[str, str]] = None
        nearest_distance = float("inf")
        for edge in self.model.edges.values():
            first, second = self.model.nodes[edge.a], self.model.nodes[edge.b]
            x1, y1, _scale1 = self._map_point(first)
            x2, y2, _scale2 = self._map_point(second)
            distance = self._distance_to_segment(event.x, event.y, x1, y1, x2, y2)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_edge = edge.key
        if nearest_edge is not None and nearest_distance <= 12:
            self.selected_node = None
            self.selected_edge_key = nearest_edge
            edge = self.model.edges[nearest_edge]
            first_name = self.model.nodes[edge.a].name
            second_name = self.model.nodes[edge.b].name
            if edge.blocked:
                state = "BLOCKED"
            elif edge.hazard > 0:
                state = f"HAZARD {edge.hazard:.0%}"
            else:
                state = "OPEN"
            self.selected_var.set(f"Connection · {first_name} ↔ {second_name} · {state}")
            self.status_var.set("Selected connection")
        else:
            self.selected_node = None
            self.selected_edge_key = None
            self.selected_var.set("No area or connection selected")
            self.status_var.set("Ready to plan")
        self.draw_map()

    def toggle_selected_edge_blocked(self) -> None:
        if self.selected_edge_key is None:
            messagebox.showinfo(
                "Select a connection",
                "Click a line between two map nodes, then click this button to block or reopen that connection.",
            )
            return
        edge = self.model.edges[self.selected_edge_key]
        if self.model.nodes[edge.a].kind == "restricted" or self.model.nodes[edge.b].kind == "restricted":
            messagebox.showinfo(
                "Restricted connection",
                "Connections to the restricted Maintenance Zone stay blocked in this demo.",
            )
            return
        edge.blocked = not edge.blocked
        first_name = self.model.nodes[edge.a].name
        second_name = self.model.nodes[edge.b].name
        state = "BLOCKED" if edge.blocked else "OPEN"
        self.selected_var.set(f"Connection · {first_name} ↔ {second_name} · {state}")
        self.status_var.set(f"Connection {state.lower()}")
        self.refresh()

    def refresh(self) -> None:
        self.node_loads, self.edge_loads = self.model._initial_loads()
        self.routes = {}
        weights = self.weights()
        algorithm = self.algorithm_var.get()
        # Route larger groups first so later groups see their estimated traffic.
        for group in sorted(self.model.groups, key=lambda item: item.people, reverse=True):
            result = self.model.make_route(group, algorithm, weights, self.node_loads, self.edge_loads)
            self.routes[group.group_id] = result
            if result.path:
                for node_id in result.path:
                    self.node_loads[node_id] = self.node_loads.get(node_id, 0.0) + group.people * 0.45
                for current, nxt in zip(result.path, result.path[1:]):
                    edge = self.model.edge_between(current, nxt)
                    if edge:
                        self.edge_loads[edge.key] = self.edge_loads.get(edge.key, 0.0) + group.people
        self.draw_map()
        self.render_legend()
        self.render_routes()
        open_exits = sum(
            1 for exit_id in self.model.exits
            if not self.model.nodes[exit_id].blocked
            and self.model.nodes[exit_id].is_open
            and self.model.nodes[exit_id].hazard < 0.70
        )
        constraint_count = sum(
            1 for node in self.model.nodes.values()
            if node.blocked or node.hazard > 0 or (node.kind == "exit" and not node.is_open)
        ) + sum(1 for edge in self.model.edges.values() if edge.blocked or edge.hazard > 0)
        self.summary_var.set(
            f"{len(self.model.groups)} groups · {sum(group.people for group in self.model.groups)} people · "
            f"{open_exits}/{len(self.model.exits)} exits available · {constraint_count} hazard/block conditions"
        )

    def route_colour_name(self, group: EvacuationGroup) -> str:
        """Return a readable colour name for the route legend and instructions."""
        return self.ROUTE_COLOR_NAMES.get(group.color.lower(), group.color)

    def render_legend(self) -> None:
        """Keep the visible route colour key synchronized with the group list."""
        for child in self.legend_frame.winfo_children():
            child.destroy()
        for index, group in enumerate(self.model.groups):
            row, column = divmod(index, 2)
            cell = tk.Frame(self.legend_frame, background=self.PANEL)
            cell.grid(row=row, column=column, sticky="w", padx=(0, 8), pady=1)
            tk.Label(
                cell,
                text="●",
                foreground=group.color,
                background=self.PANEL,
                font=("Segoe UI", 13, "bold"),
            ).pack(side="left")
            tk.Label(
                cell,
                text=f"{self.route_colour_name(group)}: {group.name}",
                foreground=self.TEXT,
                background=self.PANEL,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(3, 0))

    def _map_point(self, node: object) -> Tuple[float, float, float]:
        """Transform logical graph coordinates into the current canvas viewport."""
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 100:
            width = 760
        if height < 100:
            height = 560
        xs = [item.x for item in self.model.nodes.values()]
        ys = [item.y for item in self.model.nodes.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1.0, float(max_x - min_x))
        span_y = max(1.0, float(max_y - min_y))
        margin = 48.0
        scale = min(1.0, (width - 2 * margin) / span_x, (height - 2 * margin) / span_y)
        scale = max(0.1, scale)
        offset_x = (width - span_x * scale) / 2.0 - min_x * scale
        offset_y = (height - span_y * scale) / 2.0 - min_y * scale
        return offset_x + node.x * scale, offset_y + node.y * scale, scale

    def _on_graph_canvas_resize(self, event: tk.Event) -> None:
        size = (int(event.width), int(event.height))
        if size[0] < 100 or size[1] < 100 or size == self._last_canvas_size:
            return
        self._last_canvas_size = size
        self.draw_map()

    def toggle_group_route_colors(self) -> None:
        """Show or hide colored group-route overlays without changing routes."""
        self.show_group_route_colors = not self.show_group_route_colors
        self.route_colors_button.configure(
            text="Hide route colors" if self.show_group_route_colors else "Show route colors"
        )
        self.draw_map()

    def draw_map(self) -> None:
        self.canvas.delete("all")
        width = max(100, self.canvas.winfo_width())
        height = max(100, self.canvas.winfo_height())
        if width < 150:
            width = 760
        if height < 150:
            height = 560
        for x in range(20, width, 40):
            self.canvas.create_line(x, 10, x, height - 10, fill="#edf1f7", width=1)
        for y in range(20, height, 40):
            self.canvas.create_line(10, y, width - 10, y, fill="#edf1f7", width=1)

        # Base connections. Selected blocked connections remain visibly blocked.
        for edge in self.model.edges.values():
            start, end = self.model.nodes[edge.a], self.model.nodes[edge.b]
            x1, y1, scale = self._map_point(start)
            x2, y2, _scale2 = self._map_point(end)
            if edge.key == self.selected_edge_key and edge.blocked:
                color, dash, line_width = self.RED, (7, 4), 4
            elif edge.key == self.selected_edge_key:
                color, dash, line_width = self.TEAL, None, 5
            elif edge.blocked:
                color, dash, line_width = self.RED, (7, 4), 3
            elif edge.hazard > 0.0:
                color, dash, line_width = self.ORANGE, (3, 3), 3
            else:
                color, dash, line_width = "#90a0b5", None, 2
            kwargs = {"fill": color, "width": max(1, line_width * scale)}
            if dash:
                kwargs["dash"] = tuple(max(1, int(item * scale)) for item in dash)
            self.canvas.create_line(x1, y1, x2, y2, **kwargs)
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            label = f"{edge.length:.1f}" + (f" H{edge.hazard:.1f}" if edge.hazard > 0 else "")
            half_w = 15 * scale
            half_h = 7 * scale
            self.canvas.create_rectangle(mid_x - half_w, mid_y - half_h, mid_x + half_w, mid_y + half_h, fill="#ffffff", outline="")
            self.canvas.create_text(
                mid_x, mid_y, text=label, fill=self.ORANGE if edge.hazard > 0 else "#52647d",
                font=("Segoe UI", max(6, int(8 * scale)))
            )

        # Draw planned routes over the base graph only when the display toggle is on.
        # Hiding these overlays does not clear route data or affect any algorithm.
        if self.show_group_route_colors:
            for group in self.model.groups:
                result = self.routes.get(group.group_id)
                if not result or not result.path:
                    continue
                for current, nxt in zip(result.path, result.path[1:]):
                    start, end = self.model.nodes[current], self.model.nodes[nxt]
                    x1, y1, scale = self._map_point(start)
                    x2, y2, _scale2 = self._map_point(end)
                    self.canvas.create_line(
                        x1, y1, x2, y2, fill=group.color, width=max(2, 6 * scale), capstyle="round"
                    )
                    ratio = 0.72
                    arrow_x, arrow_y = x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio
                    r = max(2, 4 * scale)
                    self.canvas.create_oval(arrow_x - r, arrow_y - r, arrow_x + r, arrow_y + r, fill=group.color, outline="")
        kind_color = {"room": "#eaf2ff", "corridor": "#e6f6f2", "exit": "#dcfce7", "restricted": "#ede9fe"}
        short_labels = {
            "ROOM_101": "101", "AI_LAB": "AI", "LIBRARY": "LIB",
            "CORRIDOR_A": "CA", "MAIN_HALL": "HALL", "CORRIDOR_B": "CB",
            "WEST_PASSAGE": "WP", "WEST_PASSAGE_S": "WP-S",
            "STAIRWELL": "STAIR", "ATRIUM": "ATRIUM", "EAST_HALL": "E-HALL",
            "MAINTENANCE": "ZONE", "EXIT_N": "N", "EXIT_E": "E", "EXIT_S": "S",
        }
        side_labels = {"WEST_PASSAGE", "WEST_PASSAGE_S"}
        for node in self.model.nodes.values():
            x, y, scale = self._map_point(node)
            radius = (25 if node.kind != "corridor" else 27) * scale
            if node.hazard > 0:
                self.canvas.create_oval(
                    x - radius - 5 * scale, y - radius - 5 * scale,
                    x + radius + 5 * scale, y + radius + 5 * scale,
                    outline=self.ORANGE, width=max(1, 3 * scale),
                )
            unavailable_exit = node.kind == "exit" and not node.is_open
            fill = "#fee2e2" if (node.blocked or unavailable_exit or node.kind == "restricted") else kind_color.get(node.kind, "#eaf2ff")
            outline = self.TEAL if node.node_id == self.selected_node else (self.RED if node.blocked or unavailable_exit else "#7d91ad")
            self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius, fill=fill,
                outline=outline, width=max(1, (3 if node.node_id == self.selected_node else 1) * scale),
            )
            self.canvas.create_text(
                x, y, text=short_labels.get(node.node_id, node.node_id[:5]),
                fill="#1f2937", font=("Segoe UI", max(6, int(9 * scale)), "bold")
            )
            if node.blocked:
                state, state_color = "BLOCKED", self.RED
            elif unavailable_exit:
                state, state_color = "CLOSED", self.RED
            elif node.hazard > 0:
                state, state_color = f"HAZARD {node.hazard:.0%}", self.RED if node.hazard >= 0.70 else self.ORANGE
            else:
                state, state_color = "", self.MUTED
            if state:
                self.canvas.create_text(
                    x, y - radius - 8 * scale, text=state, fill=state_color,
                    font=("Segoe UI", max(6, int(7 * scale)), "bold")
                )
            if node.node_id in side_labels:
                self.canvas.create_text(
                    x - radius - 5 * scale, y, text=node.name, anchor="e",
                    fill=self.TEXT, font=("Segoe UI", max(6, int(8 * scale))), width=120 * scale
                )
            else:
                self.canvas.create_text(
                    x, y + radius + 12 * scale, text=node.name,
                    fill=self.TEXT, font=("Segoe UI", max(6, int(8 * scale)), "bold"), width=110 * scale
                )

        self.canvas.create_text(16, 15, text="NORTH", anchor="nw", fill="#64748b", font=("Segoe UI", 7, "bold"))
        self.canvas.create_text(16, height - 14, text="SOUTH", anchor="sw", fill="#64748b", font=("Segoe UI", 7, "bold"))
        self.canvas.create_text(width - 16, 15, text="LIVE MAP", anchor="ne", fill=self.TEAL, font=("Segoe UI", 7, "bold"))

    def render_routes(self) -> None:
        self.route_text.configure(state="normal")
        self.route_text.delete("1.0", "end")
        if not self.model.groups:
            self.route_text.insert("end", "No evacuation groups configured.", "muted")
            self.route_text.configure(state="disabled")
            return

        for index, group in enumerate(self.model.groups):
            result = self.routes.get(group.group_id)
            self.route_text.insert("end", f"{group.name}\n", "route_title")
            self.route_text.insert("end", f"{group.people} people  •  {result.algorithm if result else '—'}\n", "route_meta")
            self.route_text.insert(
                "end",
                f"Colour: {self.route_colour_name(group)} ({group.color})\n",
                "route_meta",
            )
            if result is None or not result.path:
                self.route_text.insert("end", f"{result.message if result else 'No route calculated'}\n", "warning")
            else:
                path_names = " → ".join(self.model.nodes[node_id].name for node_id in result.path)
                self.route_text.insert("end", f"Path: {path_names}\n", "muted")
                self.route_text.insert(
                    "end",
                    f"Distance {result.distance:.1f}  •  risk {result.risk:.0%}  •  crowd {result.crowd:.0%}\n"
                    f"Utility score: {result.utility:.0f}/100\n",
                    "muted",
                )
                self.route_text.insert("end", "Route instructions\n", "route_meta")
                for instruction in result.instructions:
                    self.route_text.insert("end", f"• {instruction}\n", "instruction")
            if index < len(self.model.groups) - 1:
                self.route_text.insert("end", "\n" + "─" * 38 + "\n\n", "muted")
        self.route_text.configure(state="disabled")


if __name__ == "__main__":
    app = EvacuationApp()
    app.mainloop()
