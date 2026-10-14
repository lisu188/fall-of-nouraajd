# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive authored hook generators using each source fixture's existing UI spies."""

from functools import wraps
import ast
import json
from pathlib import Path
from types import SimpleNamespace


def installHookFlows(api):
    namespace = api if isinstance(api, dict) else vars(api)

    def request(operation, *args, **kwargs):
        return {"operation": operation, "args": args, "kwargs": kwargs}

    def run(game, flow):
        result = None
        while True:
            try:
                pending = flow.send(result)
            except StopIteration as complete:
                return complete.value
            operation = pending["operation"]
            args, kwargs = pending.get("args", ()), pending.get("kwargs", {})
            if operation == "gui.questCommitted":
                result = None
            elif operation == "gui.checkQuests":
                result = args[0].checkQuests()
            elif operation == "gui.moveTo":
                result = args[0].moveTo(*args[1:])
            elif operation == "gui.removeObject":
                result = args[0].removeObject(args[1])
            elif operation == "gui.addObjectByName":
                result = args[0].addObjectByName(args[1], SimpleNamespace(x=args[2], y=args[3], z=args[4]))
            elif operation == "gui.addRandomLoot":
                result = game.getRngHandler().addRandomLoot(*args, **kwargs)
            elif operation.startswith("gui."):
                result = getattr(game.getGuiHandler(), operation[4:])(*args, **kwargs)
            else:
                result = namespace[operation](*args, **kwargs)

    class Hook:
        def __init__(self, callback):
            self.callback = callback

        def __set_name__(self, owner, name):
            callback = self.callback
            setattr(owner, name + "Flow", callback)

            @wraps(callback)
            def synchronous(receiver, *args, **kwargs):
                return run(receiver.getGame(), callback(receiver, *args, **kwargs))

            setattr(owner, name, synchronous)

    def receipt(*args, **kwargs):
        namespace["showRewardReceipt"](*args, **kwargs)
        yield from ()

    def remove(game_map, obj):
        if obj is not None:
            yield request("gui.removeObject", game_map, obj)

    def removeByName(game_map, name):
        yield from remove(game_map, game_map.getObjectByName(name))

    def removeMatching(game_map, predicate):
        for obj in sorted(game_map.getObjects(), key=lambda obj: obj.getName()):
            if predicate(obj):
                yield from remove(game_map, obj)

    namespace.update(
        resumableHook=Hook, uiRequest=request, flowGame=lambda game: game, uiGame=lambda game: game, runUiFlow=run
    )
    namespace.setdefault("showReader", lambda *_args, **_kwargs: None)
    namespace.update(removeObjectFlow=remove, removeObjectByNameFlow=removeByName, removeObjectsFlow=removeMatching)

    def removeRuntime(game_map, **kwargs):
        result = namespace["remove_runtime_actors"](game_map, **kwargs)
        yield from ()
        return result

    namespace["removeRuntimeActorsFlow"] = removeRuntime
    source = ast.parse((Path(__file__).resolve().parents[1] / "res/game.py").read_text(encoding="utf-8"))
    spawn = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "spawnObjectsFlow")
    spawn_namespace = {"json": json, "uiRequest": request, "Coords": lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)}
    exec(compile(ast.Module(body=[spawn], type_ignores=[]), "authored_spawn_flow", "exec"), spawn_namespace)
    namespace["spawnObjectsFlow"] = spawn_namespace["spawnObjectsFlow"]
    namespace.setdefault("showRewardReceipt", lambda *_args, **_kwargs: None)
    if "showRewardReceiptFlow" not in namespace or isinstance(namespace["showRewardReceiptFlow"], type):
        namespace["showRewardReceiptFlow"] = receipt
    campaign = namespace.get("campaign")
    if campaign is not None and not hasattr(campaign, "prepareCompletion"):
        campaign.prepareCompletion = lambda *_args, **_kwargs: None
    if campaign is not None and not hasattr(campaign, "complete_scenarioFlow"):

        def complete(*args, **kwargs):
            result = campaign.complete_scenario(*args, **kwargs)
            yield from ()
            return result

        campaign.complete_scenarioFlow = complete
    return api
