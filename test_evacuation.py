"""Automated checks for the Emergency Evacuation Planning System.
Run: python -m unittest -v
"""
import unittest

from evacuation_engine import EvacuationModel, HARD_HAZARD_THRESHOLD


DEFAULT_WEIGHTS = {"distance": 1.0, "safety": 2.6, "crowd": 1.8, "accessibility": 2.0}


class EvacuationRoutingTests(unittest.TestCase):
    def setUp(self):
        self.model = EvacuationModel()
        self.node_loads, self.edge_loads = self.model._initial_loads()

    def assert_valid_path(self, path, group, *, allow_start_hazard=True):
        self.assertIsNotNone(path)
        self.assertGreaterEqual(len(path), 2)
        self.assertEqual(path[0], group.location)
        self.assertIn(path[-1], self.model.exits)
        exit_node = self.model.nodes[path[-1]]
        self.assertTrue(exit_node.is_open)
        self.assertFalse(exit_node.blocked)
        self.assertLess(exit_node.hazard, HARD_HAZARD_THRESHOLD)
        for index, node_id in enumerate(path):
            node = self.model.nodes[node_id]
            if index == 0 and allow_start_hazard:
                pass
            else:
                self.assertFalse(node.blocked, f"Blocked node used: {node_id}")
                self.assertLess(node.hazard, HARD_HAZARD_THRESHOLD, f"Severe hazard used: {node_id}")
            if index:
                prev = path[index - 1]
                edge = self.model.edge_between(prev, node_id)
                self.assertIsNotNone(edge)
                self.assertFalse(edge.blocked, f"Blocked edge used: {prev} -> {node_id}")
                self.assertLess(edge.hazard, HARD_HAZARD_THRESHOLD, f"Severe edge hazard used: {prev} -> {node_id}")
                if group.needs_accessible:
                    self.assertTrue(edge.accessible, f"Inaccessible edge used: {prev} -> {node_id}")
                    self.assertTrue(node.accessible, f"Inaccessible node used: {node_id}")

    def test_all_three_algorithms_find_routes_in_normal_scenario(self):
        group = self.model.groups[0]
        for algorithm in ("BFS — nearest exit", "A* — crowd-aware", "Utility agent — balanced"):
            with self.subTest(algorithm=algorithm):
                result = self.model.make_route(algorithm=algorithm, group=group, weights=DEFAULT_WEIGHTS,
                                                node_loads=self.node_loads, edge_loads=self.edge_loads)
                self.assert_valid_path(result.path, group)
                self.assertTrue(result.instructions)

    def test_room_101_uses_bypass_when_corridor_a_is_on_fire(self):
        self.model.apply_scenario("Fire in north wing")
        group = next(g for g in self.model.groups if g.location == "ROOM_101")
        for algorithm in ("BFS — nearest exit", "A* — crowd-aware", "Utility agent — balanced"):
            with self.subTest(algorithm=algorithm):
                loads, edge_loads = self.model._initial_loads()
                result = self.model.make_route(group, algorithm, DEFAULT_WEIGHTS, loads, edge_loads)
                self.assert_valid_path(result.path, group)
                self.assertNotIn("CORRIDOR_A", result.path)
                self.assertNotIn("EXIT_N", result.path)

    def test_library_has_alternate_route_around_flooded_south_corridor(self):
        self.model.apply_scenario("Flooded south corridor")
        group = next(g for g in self.model.groups if g.location == "LIBRARY")
        loads, edge_loads = self.model._initial_loads()
        result = self.model.make_route(group, "A* — crowd-aware", DEFAULT_WEIGHTS, loads, edge_loads)
        self.assert_valid_path(result.path, group)
        self.assertNotIn("EXIT_S", result.path)
        self.assertNotIn("CORRIDOR_B", result.path)

    def test_bfs_never_traverses_any_marked_hazard(self):
        self.model.apply_scenario("Smoke in central hall")
        group = next(g for g in self.model.groups if g.location == "AI_LAB")
        path = self.model.bfs(group)
        self.assert_valid_path(path, group)
        self.assertNotIn("MAIN_HALL", path)
        for node_id in path[1:]:
            self.assertEqual(self.model.nodes[node_id].hazard, 0.0)
        for a, b in zip(path, path[1:]):
            self.assertEqual(self.model.edge_between(a, b).hazard, 0.0)

    def test_severe_hazard_is_impassable_to_astar_and_utility(self):
        self.model.nodes["MAIN_HALL"].hazard = HARD_HAZARD_THRESHOLD
        group = next(g for g in self.model.groups if g.location == "AI_LAB")
        for algorithm in ("A* — crowd-aware", "Utility agent — balanced"):
            with self.subTest(algorithm=algorithm):
                loads, edge_loads = self.model._initial_loads()
                result = self.model.make_route(group, algorithm, DEFAULT_WEIGHTS, loads, edge_loads)
                self.assert_valid_path(result.path, group)
                self.assertNotIn("MAIN_HALL", result.path)

    def test_accessible_group_avoids_stairs_and_north_exit(self):
        group = next(g for g in self.model.groups if g.needs_accessible)
        for algorithm in ("BFS — nearest exit", "A* — crowd-aware", "Utility agent — balanced"):
            with self.subTest(algorithm=algorithm):
                loads, edge_loads = self.model._initial_loads()
                result = self.model.make_route(group, algorithm, DEFAULT_WEIGHTS, loads, edge_loads)
                self.assert_valid_path(result.path, group)
                self.assertNotIn("STAIRWELL", result.path)
                self.assertNotIn("EXIT_N", result.path)

    def test_blocking_corridor_a_does_not_strand_room_101(self):
        group = next(g for g in self.model.groups if g.location == "ROOM_101")
        edge = self.model.edge_between("ROOM_101", "CORRIDOR_A")
        edge.blocked = True
        path = self.model.bfs(group)
        self.assert_valid_path(path, group)
        self.assertEqual(path[1], "WEST_PASSAGE")
        self.assertNotIn(("ROOM_101", "CORRIDOR_A"), list(zip(path, path[1:])))

    def test_closed_exit_is_not_used(self):
        self.model.nodes["EXIT_E"].is_open = False
        group = next(g for g in self.model.groups if g.location == "AI_LAB")
        for algorithm in ("BFS — nearest exit", "A* — crowd-aware", "Utility agent — balanced"):
            with self.subTest(algorithm=algorithm):
                loads, edge_loads = self.model._initial_loads()
                result = self.model.make_route(group, algorithm, DEFAULT_WEIGHTS, loads, edge_loads)
                self.assert_valid_path(result.path, group)
                self.assertNotEqual(result.path[-1], "EXIT_E")

    def test_no_route_is_reported_when_all_exits_are_closed(self):
        for exit_id in self.model.exits:
            self.model.nodes[exit_id].is_open = False
        group = self.model.groups[0]
        loads, edge_loads = self.model._initial_loads()
        for algorithm in ("BFS — nearest exit", "A* — crowd-aware", "Utility agent — balanced"):
            with self.subTest(algorithm=algorithm):
                result = self.model.make_route(group, algorithm, DEFAULT_WEIGHTS, loads, edge_loads)
                self.assertFalse(result.path)
                self.assertIn("No safe route", result.message)

    def test_scenario_reset_restores_map_but_maintenance_stays_restricted(self):
        self.model.apply_scenario("Multiple failures")
        self.model.apply_scenario("Normal operations")
        self.assertEqual(self.model.nodes["MAIN_HALL"].hazard, 0.0)
        self.assertTrue(self.model.nodes["EXIT_N"].is_open)
        self.assertTrue(self.model.nodes["MAINTENANCE"].blocked)
        self.assertTrue(self.model.edge_between("CORRIDOR_B", "MAINTENANCE").blocked)

    def test_every_default_group_has_a_safe_route_in_every_preset(self):
        algorithms = ("BFS — nearest exit", "A* — crowd-aware", "Utility agent — balanced")
        for scenario in self.model.SCENARIOS:
            self.model.apply_scenario(scenario)
            for algorithm in algorithms:
                loads, edge_loads = self.model._initial_loads()
                for group in self.model.groups:
                    with self.subTest(scenario=scenario, algorithm=algorithm, group=group.name):
                        result = self.model.make_route(group, algorithm, DEFAULT_WEIGHTS, loads, edge_loads)
                        self.assert_valid_path(result.path, group)
                        for node_id in result.path[1:]:
                            self.assertLess(self.model.nodes[node_id].hazard, HARD_HAZARD_THRESHOLD)
                        for first, second in zip(result.path, result.path[1:]):
                            edge = self.model.edge_between(first, second)
                            self.assertFalse(edge.blocked)
                            self.assertLess(edge.hazard, HARD_HAZARD_THRESHOLD)
                            if algorithm.startswith("BFS"):
                                self.assertEqual(edge.hazard, 0.0)

    def test_utility_score_is_bounded(self):
        group = self.model.groups[0]
        loads, edge_loads = self.model._initial_loads()
        result = self.model.make_route(group, "Utility agent — balanced", DEFAULT_WEIGHTS, loads, edge_loads)
        self.assertTrue(0 <= result.utility <= 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
