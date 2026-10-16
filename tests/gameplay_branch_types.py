# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Immutable obligations shared by the authored gameplay routes and CI planner."""

from dataclasses import dataclass
from typing import Callable

PLAYER_CLASSES = ("Warrior", "Sorcerer", "Assasin", "Inquisitor", "Wayfarer")


@dataclass(frozen=True)
class RouteCase:
    id: str
    group: str
    maps: tuple[str, ...]
    branches: tuple[str, ...]
    run: Callable
    classes: tuple[str, ...] = PLAYER_CLASSES
    race: str = "humanRace"
    initial_reputation: int | None = None
    campaign: str | None = None
    sources: tuple[str, ...] = ()
    duration_seconds: float = 200.0


def testName(case, class_id):
    return f"GameplayBranchMcpTest.test_{case.id}_{class_id}"
