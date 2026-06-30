#!/usr/bin/env python3
# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Regression coverage for GitHub #672.

Per-action iteration counts in MCP ``simulation_run`` must be bounded before any
loop executes, with a cumulative budget across the whole run, so an attacker
cannot bypass the step cap with a single extreme ``turns`` / ``times`` /
``max_iterations`` / ``max_turns`` value.

These tests use lightweight fakes for the simulation primitives so they stay
timeout-free and do not require the native ``_game`` extension. A spy event loop
records every iteration, letting us assert that a rejected action performs zero
loop iterations.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import game_simulation  # noqa: E402


class _SpyEventLoop:
    """Counts ``run`` invocations; returns False so drain loops stop quickly."""

    def __init__(self):
        self.runs = 0

    def run(self):
        self.runs += 1
        return False


class _FakeEventLoopFactory:
    def __init__(self, loop):
        self._loop = loop

    def instance(self):
        return self._loop


class _FakeGameModule:
    def __init__(self, loop):
        self.event_loop = _FakeEventLoopFactory(loop)


class _FakeMap:
    def __init__(self):
        self.moves = 0
        self.turn = 0

    def move(self):
        self.moves += 1
        self.turn += 1

    def getTurn(self):
        return self.turn

    def getPlayer(self):
        return object()


def _make_simulation():
    """Build a GameSimulation wired to spy fakes, bypassing the native engine."""
    loop = _SpyEventLoop()
    sim = object.__new__(game_simulation.GameSimulation)
    sim.gameModule = _FakeGameModule(loop)
    sim.gameMap = _FakeMap()
    sim.player = object()
    sim.mapName = "test"
    sim.playerClass = "Warrior"
    # refreshHandles re-reads map/player; keep it inert for the spy fakes.
    sim.refreshHandles = lambda: sim
    sim.playerSummary = lambda: {}
    return sim, loop


class ValidateStepsTest(unittest.TestCase):
    def _assert_rejected(self, step, field_fragment):
        with self.assertRaises(game_simulation.SimulationError) as ctx:
            game_simulation.validateSteps([step])
        self.assertIn(field_fragment, str(ctx.exception))

    # --- per-field above-limit rejection ------------------------------------
    def test_advance_turns_above_limit_rejected(self):
        self._assert_rejected({"action": "advance_turns", "turns": game_simulation.MAX_STEP_TURNS + 1}, "turns")

    def test_pump_times_above_limit_rejected(self):
        self._assert_rejected({"action": "pump_events", "times": game_simulation.MAX_STEP_PUMP_TIMES + 1}, "times")

    def test_pump_max_iterations_above_limit_rejected(self):
        self._assert_rejected(
            {"action": "pump_events", "max_iterations": game_simulation.MAX_STEP_PUMP_ITERATIONS + 1},
            "max_iterations",
        )

    def test_move_to_coords_max_turns_above_limit_rejected(self):
        self._assert_rejected(
            {"action": "move_to_coords", "max_turns": game_simulation.MAX_STEP_MOVE_TURNS + 1}, "max_turns"
        )

    def test_move_to_object_max_turns_above_limit_rejected(self):
        self._assert_rejected(
            {"action": "move_to_object", "max_turns": game_simulation.MAX_STEP_MOVE_TURNS + 1}, "max_turns"
        )

    def test_interact_object_max_turns_above_limit_rejected(self):
        self._assert_rejected(
            {"action": "interact_object", "max_turns": game_simulation.MAX_STEP_MOVE_TURNS + 1}, "max_turns"
        )

    def test_extreme_single_payload_rejected(self):
        self._assert_rejected({"action": "advance_turns", "turns": 10**9}, "turns")

    # --- boundary values just below / at the limit are accepted -------------
    def test_boundary_values_just_below_and_at_limit_accepted(self):
        self.assertTrue(
            game_simulation.validateSteps(
                [
                    {"action": "advance_turns", "turns": game_simulation.MAX_STEP_TURNS - 1},
                    {"action": "move_to_coords", "max_turns": game_simulation.MAX_STEP_MOVE_TURNS},
                ]
            )
        )

    def test_at_limit_value_accepted(self):
        self.assertTrue(
            game_simulation.validateSteps([{"action": "advance_turns", "turns": game_simulation.MAX_STEP_TURNS}])
        )

    # --- invalid types -------------------------------------------------------
    def test_non_integer_string_rejected(self):
        self._assert_rejected({"action": "advance_turns", "turns": "100"}, "integer")

    def test_float_rejected(self):
        self._assert_rejected({"action": "pump_events", "times": 3.5}, "integer")

    def test_bool_rejected(self):
        # bool is an int subclass; must be rejected explicitly.
        self._assert_rejected({"action": "advance_turns", "turns": True}, "integer")

    # --- negative / out-of-range -------------------------------------------
    def test_negative_rejected(self):
        self._assert_rejected({"action": "advance_turns", "turns": -1}, "turns")

    def test_zero_is_allowed_noop(self):
        self.assertTrue(game_simulation.validateSteps([{"action": "advance_turns", "turns": 0}]))

    # --- offending index is reported ---------------------------------------
    def test_offending_step_index_reported(self):
        with self.assertRaises(game_simulation.SimulationError) as ctx:
            game_simulation.validateSteps(
                [
                    {"action": "advance_turns", "turns": 1},
                    {"action": "advance_turns", "turns": 10**6},
                ]
            )
        self.assertEqual(ctx.exception.step, "2:advance_turns")

    # --- cumulative budget --------------------------------------------------
    def test_cumulative_budget_exhausted_across_in_bounds_steps(self):
        # Each step is individually within MAX_STEP_TURNS but their sum exceeds
        # the cumulative budget.
        per_step = game_simulation.MAX_STEP_TURNS
        count = (game_simulation.MAX_SIMULATION_ITERATION_BUDGET // per_step) + 2
        steps = [{"action": "advance_turns", "turns": per_step} for _ in range(count)]
        with self.assertRaises(game_simulation.SimulationError) as ctx:
            game_simulation.validateSteps(steps)
        self.assertIn("budget", str(ctx.exception))

    def test_repeated_actions_cannot_multiply_budget(self):
        # Repeating the same in-bounds action many times still trips the budget,
        # so nested/repeated actions cannot multiply work.
        steps = [{"action": "advance_turns", "turns": 500} for _ in range(60)]
        with self.assertRaises(game_simulation.SimulationError):
            game_simulation.validateSteps(steps)

    def test_within_budget_sequence_accepted(self):
        steps = [{"action": "advance_turns", "turns": 10} for _ in range(20)]
        self.assertTrue(game_simulation.validateSteps(steps))


class RejectedActionDoesNotLoopTest(unittest.TestCase):
    """A rejected action must perform ZERO loop iterations."""

    def test_runsteps_rejects_before_any_loop_runs(self):
        sim, loop = _make_simulation()
        with self.assertRaises(game_simulation.SimulationError):
            sim.runSteps([{"action": "advance_turns", "turns": 10**9}])
        self.assertEqual(loop.runs, 0)
        self.assertEqual(sim.gameMap.moves, 0)

    def test_rejected_step_in_sequence_runs_nothing(self):
        sim, loop = _make_simulation()
        with self.assertRaises(game_simulation.SimulationError):
            sim.runSteps(
                [
                    {"action": "advance_turns", "turns": 2},
                    {"action": "pump_events", "times": 10**9},
                ]
            )
        # Validation runs before the step loop, so even the first (valid) step
        # never executes once a later step is over-limit.
        self.assertEqual(loop.runs, 0)
        self.assertEqual(sim.gameMap.moves, 0)


class NormalGameplaySmokeTest(unittest.TestCase):
    """Legitimate small walkthroughs still run and execute the expected loops."""

    def test_small_advance_and_pump_runs_expected_iterations(self):
        sim, loop = _make_simulation()
        # advance_turns=3 -> 3 moves + 3 pumpEvents(1); pump_events times=2 -> 2 runs.
        advance = sim.advanceTurns(3)
        pumped = sim.pumpEvents(2)
        self.assertEqual(sim.gameMap.moves, 3)
        self.assertEqual(advance["turns"], 3)
        self.assertEqual(pumped["pumped"], 2)
        # 3 from advance pumps + 2 from explicit pump.
        self.assertEqual(loop.runs, 5)

    def test_validate_accepts_typical_walkthrough(self):
        steps = [
            {"action": "advance_turns", "turns": 5},
            {"action": "pump_events", "times": 1, "max_iterations": 50, "drain": True},
            {"action": "move_to_coords", "x": 1, "y": 1, "max_turns": 24},
            {"action": "read_inventory"},
            {"action": "read_map_state"},
        ]
        self.assertTrue(game_simulation.validateSteps(steps))


if __name__ == "__main__":
    unittest.main()
