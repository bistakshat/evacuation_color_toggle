"""Graph model and AI search algorithms for the Emergency Evacuation Planner.

Only Python's standard library is required.
This is an academic simulation, not a real-world emergency guidance system.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import heapq
import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# Hazards at/above this level are treated as impassable for every algorithm.
# Lower hazard levels add cost to A* and utility planning; BFS avoids any hazard.
HARD_HAZARD_THRESHOLD = 0.70


@dataclass
class Node:
    node_id: str
    name: str
    kind: str  # room, corridor, exit, restricted
    x: int
    y: int
    accessible: bool = True
    hazard: float = 0.0  # 0.0 (none) to 1.0 (extreme)
    blocked: bool = False
    base_crowd: float = 0.0
    is_open: bool = True  # Relevant to exits


@dataclass
class Edge:
    a: str
    b: str
    length: float
    width: float = 1.0
    accessible: bool = True
    hazard: float = 0.0
    blocked: bool = False
    base_crowd: float = 0.0
    base_risk: float = 0.025

    @property
    def key(self) -> Tuple[str, str]:
        return tuple(sorted((self.a, self.b)))

    def other(self, node_id: str) -> str:
        if node_id == self.a:
            return self.b
        if node_id == self.b:
            return self.a
        raise ValueError(f"Location {node_id!r} is not connected by this edge.")


@dataclass
class EvacuationGroup:
    group_id: str
    name: str
    location: str
    people: int
    needs_accessible: bool
    color: str


@dataclass
class RouteResult:
    group_id: str
    algorithm: str
    path: List[str] = field(default_factory=list)
    exit_id: Optional[str] = None
    distance: float = 0.0
    risk: float = 0.0
    crowd: float = 0.0
    accessibility: float = 1.0
    utility: float = 0.0
    search_cost: float = 0.0
    instructions: List[str] = field(default_factory=list)
    message: str = ""


class EvacuationModel:
    """Undirected building graph plus BFS, A*, and utility-based routing."""

    SCENARIOS = [
        "Normal operations",
        "Fire in north wing",
        "Flooded south corridor",
        "Smoke in central hall",
        "South exit blocked",
        "Multiple failures",
    ]

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[Tuple[str, str], Edge] = {}
        self.groups: List[EvacuationGroup] = []
        self._static_blocked_nodes: set[str] = set()
        self._static_blocked_edges: set[Tuple[str, str]] = set()
        self._build_default_map()
        self._build_default_groups()
        self.apply_scenario(self.SCENARIOS[0])

    def _add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node
        if node.blocked:
            self._static_blocked_nodes.add(node.node_id)

    def _add_edge(self, edge: Edge) -> None:
        self.edges[edge.key] = edge
        if edge.blocked:
            self._static_blocked_edges.add(edge.key)

    def _build_default_map(self) -> None:
        """Create the illustrative campus graph, including Room 101's bypass."""
        nodes = [
            Node("ROOM_101", "Room 101", "room", 100, 100, base_crowd=3),
            Node("AI_LAB", "AI Lab", "room", 100, 255, base_crowd=5),
            Node("LIBRARY", "Library", "room", 100, 410, base_crowd=4),
            Node("CORRIDOR_A", "Corridor A", "corridor", 255, 100, base_crowd=8),
            Node("MAIN_HALL", "Main Hall", "corridor", 255, 255, base_crowd=16),
            Node("CORRIDOR_B", "Corridor B", "corridor", 255, 410, base_crowd=6),
            Node("WEST_PASSAGE", "West Passage", "corridor", 175, 178, base_crowd=2),
            Node("WEST_PASSAGE_S", "West Passage South", "corridor", 175, 350, base_crowd=2),
            Node("STAIRWELL", "Stairwell", "corridor", 420, 175, accessible=False, base_crowd=5),
            Node("ATRIUM", "Atrium", "corridor", 420, 340, base_crowd=7),
            Node("EAST_HALL", "East Hall", "corridor", 535, 255, base_crowd=4),
            Node("MAINTENANCE", "Maintenance Zone", "restricted", 420, 455, blocked=True),
            Node("EXIT_N", "North Exit", "exit", 665, 90, accessible=False),
            Node("EXIT_E", "East Exit", "exit", 665, 255),
            Node("EXIT_S", "South Exit", "exit", 665, 420),
        ]
        for node in nodes:
            self._add_node(node)

        edges = [
            Edge("ROOM_101", "CORRIDOR_A", 1.3, width=1.8, base_crowd=2, base_risk=0.025),
            Edge("ROOM_101", "WEST_PASSAGE", 1.8, width=1.6, base_crowd=1, base_risk=0.02),
            Edge("WEST_PASSAGE", "MAIN_HALL", 1.6, width=1.6, base_crowd=2, base_risk=0.025),
            Edge("WEST_PASSAGE", "WEST_PASSAGE_S", 1.8, width=1.5, base_crowd=2, base_risk=0.025),
            Edge("WEST_PASSAGE_S", "MAIN_HALL", 2.5, width=1.5, base_crowd=2, base_risk=0.03),
            Edge("LIBRARY", "WEST_PASSAGE_S", 2.4, width=1.5, base_crowd=1, base_risk=0.025),
            Edge("AI_LAB", "MAIN_HALL", 1.3, width=2.0, base_crowd=5, base_risk=0.03),
            Edge("AI_LAB", "CORRIDOR_A", 2.1, width=1.4, base_crowd=3, base_risk=0.04),
            Edge("LIBRARY", "CORRIDOR_B", 1.3, width=1.8, base_crowd=2, base_risk=0.025),
            Edge("CORRIDOR_A", "MAIN_HALL", 1.5, width=1.8, base_crowd=6, base_risk=0.045),
            Edge("MAIN_HALL", "CORRIDOR_B", 1.7, width=1.8, base_crowd=4, base_risk=0.04),
            Edge("CORRIDOR_A", "EXIT_N", 2.9, width=1.5, accessible=False, base_crowd=2, base_risk=0.025),
            Edge("CORRIDOR_B", "EXIT_S", 2.8, width=1.7, base_crowd=2, base_risk=0.025),
            Edge("CORRIDOR_A", "STAIRWELL", 1.8, width=1.0, accessible=False, base_crowd=2, base_risk=0.05),
            Edge("MAIN_HALL", "STAIRWELL", 1.7, width=1.0, accessible=False, base_crowd=3, base_risk=0.05),
            Edge("STAIRWELL", "ATRIUM", 1.8, width=1.0, accessible=False, base_crowd=3, base_risk=0.05),
            Edge("ATRIUM", "EAST_HALL", 1.5, width=1.8, base_crowd=2, base_risk=0.025),
            Edge("MAIN_HALL", "EAST_HALL", 2.0, width=2.0, base_crowd=7, base_risk=0.045),
            Edge("CORRIDOR_B", "ATRIUM", 1.8, width=1.7, base_crowd=3, base_risk=0.03),
            Edge("EAST_HALL", "EXIT_E", 1.5, width=1.8, base_crowd=1, base_risk=0.025),
            Edge("CORRIDOR_B", "MAINTENANCE", 1.4, width=1.0, blocked=True, base_risk=0.1),
            Edge("MAINTENANCE", "ATRIUM", 1.5, width=1.0, blocked=True, base_risk=0.1),
        ]
        for edge in edges:
            self._add_edge(edge)

    def _build_default_groups(self) -> None:
        self.groups = [
            EvacuationGroup("g1", "Group A", "ROOM_101", 3, False, "#2563eb"),
            EvacuationGroup("g2", "Group B", "AI_LAB", 5, False, "#b45309"),
            EvacuationGroup("g3", "Group C", "LIBRARY", 2, False, "#7c3aed"),
            EvacuationGroup("g4", "Care Unit", "EAST_HALL", 6, True, "#be123c"),
        ]

    @property
    def exits(self) -> List[str]:
        return [node.node_id for node in self.nodes.values() if node.kind == "exit"]

    def neighbors(self, node_id: str) -> Iterable[Tuple[str, Edge]]:
        for edge in self.edges.values():
            if edge.a == node_id or edge.b == node_id:
                yield edge.other(node_id), edge

    def edge_between(self, first: str, second: str) -> Optional[Edge]:
        return self.edges.get(tuple(sorted((first, second))))

    def reset_dynamic_state(self) -> None:
        """Clear simulated hazards and restore fixed restricted areas/edges."""
        for node in self.nodes.values():
            node.hazard = 0.0
            node.blocked = node.node_id in self._static_blocked_nodes
            node.is_open = True
        for edge in self.edges.values():
            edge.hazard = 0.0
            edge.blocked = edge.key in self._static_blocked_edges

    def apply_scenario(self, scenario: str) -> None:
        self.reset_dynamic_state()
        if scenario == "Normal operations":
            return
        if scenario == "Fire in north wing":
            self.nodes["CORRIDOR_A"].hazard = 0.92
            self.edges[tuple(sorted(("ROOM_101", "CORRIDOR_A")))].hazard = 0.82
            self.nodes["EXIT_N"].is_open = False
        elif scenario == "Flooded south corridor":
            # A serious but not fully impassable flood warning is represented as
            # a high soft cost; the South Exit connection is closed.
            self.nodes["CORRIDOR_B"].hazard = 0.82
            self.edges[tuple(sorted(("CORRIDOR_B", "EXIT_S")))].blocked = True
            self.edges[tuple(sorted(("LIBRARY", "CORRIDOR_B")))].hazard = 0.28
        elif scenario == "Smoke in central hall":
            self.nodes["MAIN_HALL"].hazard = 0.78
            for pair in (("AI_LAB", "MAIN_HALL"), ("WEST_PASSAGE", "MAIN_HALL"), ("MAIN_HALL", "CORRIDOR_B")):
                self.edges[tuple(sorted(pair))].hazard = 0.48
        elif scenario == "South exit blocked":
            self.nodes["EXIT_S"].is_open = False
            self.edges[tuple(sorted(("CORRIDOR_B", "EXIT_S")))].blocked = True
        elif scenario == "Multiple failures":
            self.nodes["MAIN_HALL"].hazard = 0.82
            self.nodes["EXIT_N"].is_open = False
            self.edges[tuple(sorted(("CORRIDOR_B", "EXIT_S")))].blocked = True
            self.edges[tuple(sorted(("ROOM_101", "CORRIDOR_A")))].hazard = 0.45
            self.edges[tuple(sorted(("MAIN_HALL", "EAST_HALL")))].hazard = 0.52
        else:
            raise ValueError(f"Unknown emergency scenario: {scenario}")

    @staticmethod
    def _is_hard_hazard(value: float) -> bool:
        return value >= HARD_HAZARD_THRESHOLD

    def _node_is_hard_unusable(self, node_id: str) -> bool:
        node = self.nodes[node_id]
        if node.blocked or node.kind == "restricted" or self._is_hard_hazard(node.hazard):
            return True
        if node.kind == "exit" and not node.is_open:
            return True
        return False

    def _can_enter(self, node_id: str, group: EvacuationGroup, start: str) -> bool:
        node = self.nodes[node_id]
        # A group may leave its current location even if that location is
        # hazardous/blocked; it may not enter another unusable location.
        if node_id != start and self._node_is_hard_unusable(node_id):
            return False
        if node_id != start and group.needs_accessible and not node.accessible:
            return False
        return True

    def _can_use_edge(self, edge: Edge, group: EvacuationGroup) -> bool:
        if edge.blocked or self._is_hard_hazard(edge.hazard):
            return False
        if group.needs_accessible and not edge.accessible:
            return False
        return True

    def _edge_is_hazardous_for_bfs(self, edge: Edge) -> bool:
        return edge.hazard > 0.0

    def _node_is_hazardous_for_bfs(self, node_id: str) -> bool:
        return self.nodes[node_id].hazard > 0.0

    def _is_usable_exit(self, exit_id: str, group: EvacuationGroup, start: str, *, bfs: bool = False) -> bool:
        node = self.nodes[exit_id]
        if node.kind != "exit" or not self._can_enter(exit_id, group, start):
            return False
        if bfs and self._node_is_hazardous_for_bfs(exit_id):
            return False
        return True

    def _iter_valid_neighbors(
        self, node_id: str, group: EvacuationGroup, start: str, *, bfs: bool = False,
    ) -> Iterable[Tuple[str, Edge]]:
        for nxt, edge in self.neighbors(node_id):
            if not self._can_use_edge(edge, group):
                continue
            if bfs and self._edge_is_hazardous_for_bfs(edge):
                continue
            if nxt != start and not self._can_enter(nxt, group, start):
                continue
            if bfs and nxt != start and self._node_is_hazardous_for_bfs(nxt):
                continue
            yield nxt, edge

    def _usable_exits(self, group: EvacuationGroup, start: str, *, bfs: bool = False) -> List[str]:
        return [exit_id for exit_id in self.exits if self._is_usable_exit(exit_id, group, start, bfs=bfs)]

    def bfs(self, group: EvacuationGroup) -> Optional[List[str]]:
        """Find the route with fewest edges; any marked hazard is avoided."""
        start = group.location
        if start not in self.nodes:
            return None
        targets = set(self._usable_exits(group, start, bfs=True))
        if not targets:
            return None
        queue = deque([start])
        previous: Dict[str, Optional[str]] = {start: None}
        while queue:
            current = queue.popleft()
            if current in targets and current != start:
                return self._reconstruct(previous, current)
            for nxt, _edge in self._iter_valid_neighbors(current, group, start, bfs=True):
                if nxt not in previous:
                    previous[nxt] = current
                    queue.append(nxt)
        return None

    def _heuristic(self, node_id: str, group: EvacuationGroup, weights: Dict[str, float], start: str) -> float:
        """Admissible geometric lower bound based only on distance cost."""
        distance_weight = max(0.0, weights.get("distance", 1.0))
        if distance_weight <= 0.0:
            return 0.0
        possible_exits = self._usable_exits(group, start, bfs=False)
        if not possible_exits:
            return 0.0
        ratios: List[float] = []
        for edge in self.edges.values():
            pixel_distance = math.hypot(
                self.nodes[edge.a].x - self.nodes[edge.b].x,
                self.nodes[edge.a].y - self.nodes[edge.b].y,
            )
            if pixel_distance > 0 and edge.length >= 0:
                ratios.append((edge.length * distance_weight) / pixel_distance)
        scale = min(ratios) if ratios else 0.0
        return scale * min(
            math.hypot(self.nodes[node_id].x - self.nodes[exit_id].x,
                       self.nodes[node_id].y - self.nodes[exit_id].y)
            for exit_id in possible_exits
        )

    def _initial_loads(self) -> Tuple[Dict[str, float], Dict[Tuple[str, str], float]]:
        node_loads = {node_id: float(node.base_crowd) for node_id, node in self.nodes.items()}
        edge_loads = {edge.key: float(edge.base_crowd) for edge in self.edges.values()}
        for group in self.groups:
            if group.location in node_loads:
                node_loads[group.location] += group.people
        return node_loads, edge_loads

    def _step_metrics(
        self,
        current: str,
        nxt: str,
        edge: Edge,
        node_loads: Dict[str, float],
        edge_loads: Dict[Tuple[str, str], float],
    ) -> Tuple[float, float, float, float]:
        """Return route length, hazard/risk, crowd density, and accessibility."""
        next_node = self.nodes[nxt]
        risk = min(1.0, edge.base_risk + next_node.hazard * 0.65 + edge.hazard * 0.35)
        capacity = max(1.0, edge.width * 16.0)
        crowd = min(
            1.0,
            (edge_loads.get(edge.key, 0.0) + node_loads.get(nxt, 0.0) * 0.35) / capacity,
        )
        accessible = 1.0 if edge.accessible and next_node.accessible else 0.0
        return edge.length, risk, crowd, accessible

    def _step_cost(
        self, current: str, nxt: str, edge: Edge, weights: Dict[str, float],
        node_loads: Dict[str, float], edge_loads: Dict[Tuple[str, str], float],
    ) -> float:
        distance, risk, crowd, accessible = self._step_metrics(current, nxt, edge, node_loads, edge_loads)
        w_distance = max(0.0, weights.get("distance", 1.0))
        w_safety = max(0.0, weights.get("safety", 2.6))
        w_crowd = max(0.0, weights.get("crowd", 1.8))
        w_access = max(0.0, weights.get("accessibility", 2.0))
        return (
            w_distance * distance
            + w_safety * distance * (0.15 + 4.0 * risk)
            + w_crowd * distance * (3.0 * crowd)
            + w_access * distance * (1.0 - accessible) * 8.0
        )

    def astar(
        self,
        group: EvacuationGroup,
        weights: Dict[str, float],
        node_loads: Dict[str, float],
        edge_loads: Dict[Tuple[str, str], float],
    ) -> Tuple[Optional[List[str]], float]:
        """A* minimizes weighted distance, risk, crowd and access penalty."""
        start = group.location
        if start not in self.nodes:
            return None, float("inf")
        targets = set(self._usable_exits(group, start, bfs=False))
        if not targets:
            return None, float("inf")
        counter = 0
        queue: List[Tuple[float, int, float, str]] = [
            (self._heuristic(start, group, weights, start), counter, 0.0, start)
        ]
        previous: Dict[str, Optional[str]] = {start: None}
        best_cost: Dict[str, float] = {start: 0.0}
        while queue:
            _priority, _counter, current_cost, current = heapq.heappop(queue)
            if current_cost > best_cost.get(current, float("inf")) + 1e-9:
                continue
            if current in targets and current != start:
                return self._reconstruct(previous, current), current_cost
            for nxt, edge in self._iter_valid_neighbors(current, group, start, bfs=False):
                new_cost = current_cost + self._step_cost(current, nxt, edge, weights, node_loads, edge_loads)
                if new_cost + 1e-9 < best_cost.get(nxt, float("inf")):
                    best_cost[nxt] = new_cost
                    previous[nxt] = current
                    counter += 1
                    estimate = self._heuristic(nxt, group, weights, start)
                    heapq.heappush(queue, (new_cost + estimate, counter, new_cost, nxt))
        return None, float("inf")

    def _all_simple_exit_paths(self, group: EvacuationGroup, limit: int = 5000) -> List[List[str]]:
        """Enumerate viable simple paths (bounded for safety on larger graphs)."""
        paths: List[List[str]] = []
        start = group.location
        if start not in self.nodes:
            return paths
        if not self._usable_exits(group, start, bfs=False):
            return paths

        def visit(current: str, path: List[str], seen: set[str]) -> None:
            if len(paths) >= limit:
                return
            if current in self.exits and current != start:
                if self._is_usable_exit(current, group, start, bfs=False):
                    paths.append(path[:])
                return
            for nxt, _edge in self._iter_valid_neighbors(current, group, start, bfs=False):
                if nxt in seen:
                    continue
                visit(nxt, path + [nxt], seen | {nxt})
                if len(paths) >= limit:
                    return

        visit(start, [start], {start})
        return paths

    def path_metrics(
        self, path: Sequence[str], group: EvacuationGroup,
        node_loads: Dict[str, float], edge_loads: Dict[Tuple[str, str], float],
    ) -> Tuple[float, float, float, float]:
        distance_total = 0.0
        risks: List[float] = []
        crowds: List[float] = []
        access_values: List[float] = []
        for current, nxt in zip(path, path[1:]):
            edge = self.edge_between(current, nxt)
            if edge is None:
                continue
            distance, risk, crowd, accessible = self._step_metrics(current, nxt, edge, node_loads, edge_loads)
            distance_total += distance
            risks.append(risk)
            crowds.append(crowd)
            access_values.append(accessible)
        return (
            distance_total,
            sum(risks) / len(risks) if risks else 0.0,
            sum(crowds) / len(crowds) if crowds else 0.0,
            sum(access_values) / len(access_values) if access_values else 1.0,
        )

    def utility_route(
        self,
        group: EvacuationGroup,
        weights: Dict[str, float],
        node_loads: Dict[str, float],
        edge_loads: Dict[Tuple[str, str], float],
    ) -> Tuple[Optional[List[str]], float]:
        """Choose the highest-utility viable path after comparing route metrics."""
        candidates = self._all_simple_exit_paths(group)
        if not candidates:
            return None, float("inf")
        metrics = [self.path_metrics(path, group, node_loads, edge_loads) for path in candidates]
        max_distance = max((m[0] for m in metrics), default=1.0) or 1.0
        max_risk = max(0.15, max((m[1] for m in metrics), default=0.15))
        max_crowd = max(0.15, max((m[2] for m in metrics), default=0.15))
        w = {key: max(0.0, weights.get(key, 1.0)) for key in ("distance", "safety", "crowd", "accessibility")}
        total_weight = sum(w.values())
        if total_weight <= 1e-9:
            # If all sliders are zero, make the behavior deterministic and useful.
            w["distance"] = 1.0
            total_weight = 1.0

        best_path: Optional[List[str]] = None
        best_penalty = float("inf")
        for path, (distance, risk, crowd, accessibility) in zip(candidates, metrics):
            normalized_penalty = (
                w["distance"] * (distance / max_distance)
                + w["safety"] * (risk / max_risk)
                + w["crowd"] * (crowd / max_crowd)
                + w["accessibility"] * (1.0 - accessibility)
            ) / total_weight
            if normalized_penalty < best_penalty:
                best_penalty = normalized_penalty
                best_path = path
        return best_path, best_penalty

    def make_route(
        self,
        group: EvacuationGroup,
        algorithm: str,
        weights: Dict[str, float],
        node_loads: Dict[str, float],
        edge_loads: Dict[Tuple[str, str], float],
    ) -> RouteResult:
        if algorithm == "BFS — nearest exit":
            path = self.bfs(group)
            search_cost = float(len(path) - 1) if path else float("inf")
            short_name = "BFS"
        elif algorithm == "A* — crowd-aware":
            path, search_cost = self.astar(group, weights, node_loads, edge_loads)
            short_name = "A*"
        else:
            path, search_cost = self.utility_route(group, weights, node_loads, edge_loads)
            short_name = "UTILITY"

        result = RouteResult(group.group_id, short_name)
        if not path:
            result.message = "No safe route to an open exit under the current constraints."
            return result

        distance, risk, crowd, accessibility = self.path_metrics(path, group, node_loads, edge_loads)
        result.path = list(path)
        result.exit_id = path[-1]
        result.distance = distance
        result.risk = risk
        result.crowd = crowd
        result.accessibility = accessibility
        result.search_cost = search_cost
        if short_name == "UTILITY":
            result.utility = max(0.0, min(100.0, 100.0 * (1.0 - search_cost)))
        else:
            result.utility = max(
                0.0,
                min(100.0, 100.0 - (risk * max(0.0, weights.get("safety", 1.0))
                                     + crowd * max(0.0, weights.get("crowd", 1.0))) * 22.0
                      - distance * max(0.0, weights.get("distance", 1.0)) * 3.0),
            )
        result.instructions = self.build_instructions(group, path)
        return result

    def build_instructions(self, group: EvacuationGroup, path: Sequence[str]) -> List[str]:
        if not path:
            return ["No safe route is currently available.", "Review the hazard and exit status; do not force a route through a blocked or severe hazard."]
        instructions = [f"Start at {self.nodes[path[0]].name} with {group.people} people."]
        for current, nxt in zip(path, path[1:]):
            edge = self.edge_between(current, nxt)
            if edge is None:
                continue
            next_node = self.nodes[nxt]
            dx = next_node.x - self.nodes[current].x
            dy = next_node.y - self.nodes[current].y
            if abs(dx) >= abs(dy):
                direction = "east/right" if dx >= 0 else "west/left"
            else:
                direction = "south/down" if dy >= 0 else "north/up"
            if next_node.kind == "exit":
                instruction = f"Move {direction} for {edge.length:.1f} route units to {next_node.name}, then exit."
            else:
                instruction = f"Move {direction} for {edge.length:.1f} route units toward {next_node.name}."
            if edge.hazard > 0.0 or next_node.hazard > 0.0:
                instruction += " Caution: this segment has a hazard penalty."
            if group.needs_accessible:
                instruction += " Follow the accessible path."
            instructions.append(instruction)
        instructions.append("Once outside, proceed to the designated safe assembly area.")
        return instructions

    def _reconstruct(self, previous: Dict[str, Optional[str]], current: str) -> List[str]:
        path: List[str] = []
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()
        return path
