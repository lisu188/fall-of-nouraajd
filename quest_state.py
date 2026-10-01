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
from functools import wraps

QUEST_JOURNAL_VERSION = 1
QUEST_JOURNAL_UNAVAILABLE_HINT = "This older save has no recorded outcome details for this quest."


def mapQuest(source_map):
    """Keep a map quest's journal on the quest that travels with the player.

    source_map is a map id, or a resolver for configured instances sharing a class.
    A hasLegacyJournal method may opt into reading already-persistent outcome data.
    """

    def decorate(cls):
        originals = {name: getattr(cls, name) for name in ("isCompleted", "getObjective", "getReward", "getHint")}
        authored_text = {
            name for name in ("getObjective", "getReward", "getHint") if hasattr(originals[name], "__code__")
        }
        if not hasattr(originals["isCompleted"], "__code__"):
            originals["isCompleted"] = lambda _quest: False

        def origin(quest):
            return source_map(quest) if callable(source_map) else source_map

        def currentMap(quest):
            game = quest.getGame()
            return game.getMap() if game is not None else None

        def onSource(quest):
            game_map = currentMap(quest)
            return game_map is not None and game_map.mapName == origin(quest)

        def hasSnapshot(quest):
            return quest.getNumericProperty("questJournalVersion") == QUEST_JOURNAL_VERSION and quest.getStringProperty(
                "questJournalOrigin"
            ) == origin(quest)

        def membership(quest):
            game_map = currentMap(quest)
            player = game_map.getPlayer() if game_map is not None else None
            if player is not None:
                if hasattr(player, "getCompletedQuests") and quest in player.getCompletedQuests():
                    return True
                if hasattr(player, "getQuests") and quest in player.getQuests():
                    return False
            return None

        def hasLegacy(quest):
            return bool(getattr(quest, "hasLegacyJournal", lambda: False)())

        def neutralText(quest, name, completed=None):
            if name == "getHint":
                return QUEST_JOURNAL_UNAVAILABLE_HINT
            if name == "getReward":
                return "Reward details are unavailable in this older save."
            description = quest.getDescription() or "Quest"
            completed = membership(quest) if completed is None else completed
            if completed:
                return description + " Completed; outcome details are unavailable."
            return description + " Progress details are unavailable."

        def journalText(quest, name):
            snapshot = hasSnapshot(quest)
            if snapshot and (quest.getBoolProperty("questJournalCompleted") or not onSource(quest)):
                return quest.getStringProperty("questJournal" + name.removeprefix("get"))
            if onSource(quest):
                if membership(quest) is not True or originals["isCompleted"](quest):
                    return originals[name](quest)
            elif hasLegacy(quest):
                return originals[name](quest)
            return neutralText(quest, name)

        @wraps(originals["isCompleted"])
        def isCompleted(self):
            if hasSnapshot(self) and self.getBoolProperty("questJournalCompleted"):
                return True
            completed = membership(self)
            if completed is True:
                return True
            if onSource(self):
                return originals["isCompleted"](self)
            if completed is not None:
                return completed
            return bool(hasLegacy(self) and originals["isCompleted"](self))

        def captureJournal(self, completed):
            if hasSnapshot(self) and self.getBoolProperty("questJournalCompleted"):
                return
            source = onSource(self)
            legacy = not source and hasLegacy(self)
            if source or legacy:
                if completed and membership(self) is True and not originals["isCompleted"](self):
                    values = [neutralText(self, name, completed) for name in ("getObjective", "getReward", "getHint")]
                else:
                    values = [originals[name](self) for name in ("getObjective", "getReward", "getHint")]
            elif hasSnapshot(self):
                self.setBoolProperty("questJournalCompleted", bool(completed))
                return
            else:
                # Keep a missing legacy snapshot recoverable when its source becomes available.
                return
            if not all(isinstance(value, str) for value in values):
                raise TypeError("Quest journal text must be strings")
            source_id = origin(self)
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("Quest journal requires a source map id")
            for suffix, value in zip(("Objective", "Reward", "Hint"), values):
                self.setStringProperty("questJournal" + suffix, value)
            self.setStringProperty("questJournalOrigin", source_id)
            self.setBoolProperty("questJournalCompleted", bool(completed))
            self.setNumericProperty("questJournalVersion", QUEST_JOURNAL_VERSION)

        def wrapText(name):
            @wraps(originals[name])
            def getter(self):
                return journalText(self, name)

            return getter

        cls.isCompleted = isCompleted
        cls.captureJournal = captureJournal
        # Native default getters already read quest-owned fields; wrapping them would re-enter virtual dispatch.
        for name in authored_text:
            setattr(cls, name, wrapText(name))
        return cls

    return decorate


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
