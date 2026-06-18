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

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyBoolFlag:
    name: str
    quest: str
    states: tuple[str, ...] = ()
    excluded_states: tuple[str, ...] = ()
    predicate: object = None

    def evaluate(self, state):
        if self.predicate is not None:
            return bool(self.predicate(state))
        if self.excluded_states:
            return state not in self.excluded_states
        return state in self.states


class QuestStateStore:
    QUEST_KEYS = {}
    QUEST_DEFAULTS = {}
    QUEST_NUMERIC_DEFAULTS = {}
    LEGACY_BOOL_FLAGS = ()

    def __init__(self, game_map):
        self.map = game_map

    def is_stale(self, game_map):
        return self.map != game_map

    def key(self, quest):
        return self.QUEST_KEYS[quest]

    def get_state(self, quest):
        state = self.map.getStringProperty(self.key(quest))
        if not state:
            state = self.QUEST_DEFAULTS[quest]
            self.map.setStringProperty(self.key(quest), state)
        return state

    def set_state(self, quest, state, sync=True):
        self.map.setStringProperty(self.key(quest), state)
        if sync:
            self.sync_legacy_flags()

    def _set_state(self, quest, state, sync=True):
        self.set_state(quest, state, sync=sync)

    def reset_all(self):
        for quest, state in self.QUEST_DEFAULTS.items():
            self.map.setStringProperty(self.key(quest), state)
        self.reset_numeric_defaults()
        self.sync_legacy_flags()

    def initialize_defaults(self):
        changed = False
        for quest, state in self.QUEST_DEFAULTS.items():
            if not self.map.getStringProperty(self.key(quest)):
                self.map.setStringProperty(self.key(quest), state)
                changed = True
        if changed:
            self.reset_numeric_defaults()
            self.sync_legacy_flags()
        return changed

    def reset_numeric_defaults(self):
        for name, value in self.QUEST_NUMERIC_DEFAULTS.items():
            self.map.setNumericProperty(name, value)

    def sync_legacy_flags(self):
        for flag in self.LEGACY_BOOL_FLAGS:
            self.map.setBoolProperty(flag.name, flag.evaluate(self.get_state(flag.quest)))

    def _sync_legacy_flags(self):
        self.sync_legacy_flags()

    def state_in(self, quest, states):
        return self.get_state(quest) in states


class TrackedQuest:
    def __init__(self, name):
        self._name = name

    def getName(self):
        return self._name

    def getTypeId(self):
        return self._name


class PlayerQuestRegistry:
    def __init__(self):
        self._quests = {}

    def reset(self, _player=None):
        self._quests.clear()

    def install_on(self, player_cls):
        if hasattr(player_cls, "getQuests"):
            return
        registry = self

        def get_quests(_player):
            return list(registry._quests.values())

        player_cls.getQuests = get_quests

    def remember(self, quest_name):
        self._quests[quest_name] = TrackedQuest(quest_name)


def quest_id(quest):
    if hasattr(quest, "getTypeId"):
        quest_type = quest.getTypeId()
        if quest_type:
            return quest_type
    return quest.getName()


def player_has_quest(player, quest_name, registry=None):
    if hasattr(player, "getQuests"):
        return any(quest_id(quest) == quest_name for quest in player.getQuests())
    if registry is not None:
        return quest_name in registry._quests
    return False


def ensure_quest(player, quest_name, registry=None):
    if player_has_quest(player, quest_name, registry=registry):
        return False
    player.addQuest(quest_name)
    if registry is not None:
        registry.remember(quest_name)
    return True
