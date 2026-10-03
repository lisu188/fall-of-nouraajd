# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import game
import json
from json import JSONDecodeError
from game import campaign, narrative


def assertSafe(function):
    namespace = getattr(function, "__globals__", {})
    builtins = namespace.get("__builtins__", {})
    assert isinstance(builtins, dict) and "open" not in builtins
    assert not hasattr(function, "__wrapped__")


def assertSafeError(error):
    assert error.__context__ is None and error.__cause__ is None
    frame = error.__traceback__
    while frame is not None:
        builtins = frame.tb_frame.f_globals.get("__builtins__", {})
        assert isinstance(builtins, dict) and "open" not in builtins
        frame = frame.tb_next


def load(_unused, context):
    assertSafe(json.loads)
    assertSafe(json.dumps)
    assertSafe(JSONDecodeError.__init__)
    assert not hasattr(json, "JSONDecoder")
    assert json.loads(json.dumps({"probe": [1, True, None]})) == {"probe": [1, True, None]}
    try:
        json.loads("{")
    except JSONDecodeError as error:
        assert (error.pos, error.lineno, error.colno) == (1, 1, 2)
        assert error.msg and error.doc == "{"
        assertSafeError(error)
    else:
        assert False

    def reject(value):
        raise ValueError("callback rejected")

    try:
        json.dumps(set(), default=reject)
    except ValueError as error:
        assertSafeError(error)
    else:
        assert False

    assertSafe(campaign.state)
    assertSafe(narrative.getVariable)
    assert not hasattr(campaign, "load_manifest")
    assert not hasattr(campaign, "Path")
    store = campaign.state(context)
    assert store is not None
    assertSafe(store.get_var)
    store.set_var("proxyProbe", "ready")
    assert store.get_var("proxyProbe") == "ready"
    assert narrative.getVariable(context, "proxyProbe") == "ready"
    try:
        store.set_var("invalid-name", "value")
    except ValueError as error:
        assertSafeError(error)
    else:
        assert False

    class FakeGame:
        pass

    for operation in (campaign.state, campaign.retryPending):
        try:
            operation(FakeGame())
        except TypeError:
            pass
        else:
            assert False
    try:
        game.craftRecipe(FakeGame(), None, "unknown")
    except TypeError:
        pass
    else:
        assert False

    assertSafe(game.CDialog._get_public_callback)

    class Dialog(game.CDialog):
        def open(self):
            self.opened = True

        def ready(self):
            return True

    dialog = Dialog()
    assert dialog.invokeAction("open") and dialog.opened
    assert dialog.invokeCondition("ready")
    assert not dialog.invokeAction("missing")
    assert not dialog.invokeCondition("_get_public_callback")
    assertSafe(game.register(context))
    assertSafe(game.mapQuest("test"))
    assertSafe(game.proxyClosureProbe)
    assert game.proxyClosureProbe() == 42
    assertSafe(game.proxyDefaultProbe)
    callback = game.proxyDefaultProbe()
    assertSafe(callback)
    assert callback() == 42

    @game.mapQuest("test")
    class JournalProbe:
        def isCompleted(self):
            return False

        def getObjective(self):
            return "objective"

        def getReward(self):
            return "reward"

        def getHint(self):
            return "hint"

    assertSafe(JournalProbe.isCompleted)
    assertSafe(JournalProbe.captureJournal)
    assertSafe(JournalProbe.getObjective)

    assertSafe(game.LegacyBoolFlag.__init__)
    assert not hasattr(game.LegacyBoolFlag, "__dataclass_fields__")
    flag = game.LegacyBoolFlag("flag", "quest", ("ready",))
    assert flag.evaluate("ready")
    try:
        flag.name = "changed"
    except Exception:
        pass
    else:
        assert False

    class Player:
        pass

    registry = game.PlayerQuestRegistry()
    registry.install_on(player_cls=Player)
    assertSafe(Player.getQuests)
    registry.remember("probeQuest")
    quest = registry._quests["probeQuest"]
    assertSafe(quest.getName)
    assert quest.getName() == "probeQuest"
    assertSafe(game.QuestStateStore.__init__)
    assertSafe(game.ensure_quest)

    class CaptureMap:
        def forObjects(self, append, predicate):
            self.predicate = predicate

    capture = CaptureMap()
    assert game.remove_runtime_actors(capture, names=("probe",)) == 0
    assertSafe(capture.predicate)
    context.setBoolProperty("proxyRuntimeProbePassed", True)
