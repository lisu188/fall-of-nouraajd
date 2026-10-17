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

"""Heroes III-style multi-scenario campaign driver.

A campaign is a DAG of scenario maps declared in
``res/campaigns/<campaignId>/campaign.json`` (see
``docs/design/multilevel_campaign.md``).  Map scripts report how a scenario
ended via :func:`complete_scenario`; the manifest — not the map — decides which
map comes next.  Campaign position and cross-scenario variables are stored as
dynamic properties on the player object, which is the only object that crosses
map transitions and is embedded in every save, so campaign progress survives
save/load without any save-format change.

This module deliberately imports nothing from ``_game`` at module level: the
manifest handling, routing, carryover, and state-store logic are plain Python
so they stay unit-testable before the native extension is built.  Only
:func:`start` touches the engine loader, and it imports it lazily.
"""

from __future__ import annotations

import json
from pathlib import Path
from weakref import WeakKeyDictionary

CAMPAIGN_FORMAT = "fall-of-nouraajd-campaign"
CAMPAIGN_SCHEMA_VERSION = 1
CAMPAIGN_MANIFEST_NAME = "campaign.json"

# Player dynamic properties. The ``campaign_`` prefix is an allowlisted dynamic
# property namespace (scripts/validate_content.py REVIEWED_DYNAMIC_PROPERTY_PREFIXES).
# ``campaign_finished`` intentionally differs from the ``campaign_completed`` *map*
# bool the siege script sets, so map-local and campaign-level completion stay distinct.
CAMPAIGN_ID_PROPERTY = "campaign_id"
CAMPAIGN_SCENARIO_PROPERTY = "campaign_scenario"
CAMPAIGN_FINISHED_PROPERTY = "campaign_finished"
CAMPAIGN_HISTORY_PROPERTY = "campaign_history"
CAMPAIGN_VAR_PREFIX = "campaign_var_"
CAMPAIGN_PENDING_PROPERTY = "campaign_pendingTransition"
_INFLIGHT_TRANSITIONS = WeakKeyDictionary()
_INFLIGHT_PRESENTATIONS = WeakKeyDictionary()


class _TransitionGuard:
    def __init__(self, game):
        self.game = game


class _CompletionOwner:
    def __init__(self, game, store):
        from ui import flowGame

        self.game = flowGame(game)
        self.map = game.getMap()
        self.player = store.player
        self.campaign = store.campaign_id()
        self.scenario = store.scenario()
        self.finished = store.finished()
        self.history = store.history()
        self.pending = self.player.getStringProperty(CAMPAIGN_PENDING_PROPERTY)
        getter = getattr(game, "getContext", None)
        self.context = getter() if callable(getter) else None
        capture = getattr(self.context, "captureTransitionGeneration", None)
        self.generation = capture() if callable(capture) else None

    def isCurrent(self, check_generation=True):
        try:
            if self.context is not None:
                if not self.context.isActive():
                    return False
                if check_generation and self.generation is not None:
                    if not self.context.isTransitionGenerationCurrent(self.generation):
                        return False
            current_map = self.game.getMap()
            if current_map is not self.map or current_map is None or current_map.getPlayer() is not self.player:
                return False
            store = CampaignStateStore(self.player)
            return (
                store.campaign_id() == self.campaign
                and store.scenario() == self.scenario
                and store.finished() == self.finished
                and store.history() == self.history
                and self.player.getStringProperty(CAMPAIGN_PENDING_PROPERTY) == self.pending
            )
        except RuntimeError:
            return False


def _callbackGame(game):
    from ui import UiFlowGame

    if isinstance(game, UiFlowGame):
        return game
    create_resolver = getattr(game, "createWeakResolver", None)
    return UiFlowGame(create_resolver()) if callable(create_resolver) else game


def _transitionInFlight(game):
    return _operationInFlight(game, _INFLIGHT_TRANSITIONS)


def _operationInFlight(game, operations):
    from ui import uiGame

    owner = uiGame(game)
    for guard in operations:
        try:
            if uiGame(guard.game) is owner:
                return True
        except RuntimeError:
            # Native weak resolvers reject an owner destroyed while its request is being cancelled.
            continue
    return False


# Carryover policy keys supported at scenario entry. ``gold_max`` clamps gold,
# the item filters keep/strip inventory by config id. Exactly one of
# items_allow/items_deny may be present.
CARRYOVER_GOLD_MAX = "gold_max"
CARRYOVER_ITEMS_ALLOW = "items_allow"
CARRYOVER_ITEMS_DENY = "items_deny"
CARRYOVER_KEYS = (CARRYOVER_GOLD_MAX, CARRYOVER_ITEMS_ALLOW, CARRYOVER_ITEMS_DENY)

SCENARIO_REQUIRED_KEYS = ("map", "title", "briefing", "next")
SCENARIO_KEYS = ("map", "title", "briefing", "epilogue", "carryover", "next", "artwork")
MANIFEST_REQUIRED_KEYS = ("format", "schemaVersion", "campaignId", "title", "start", "scenarios")
MANIFEST_KEYS = MANIFEST_REQUIRED_KEYS + ("description", "completionText", "artwork")


class CampaignError(ValueError):
    """A campaign manifest or campaign runtime state is invalid."""


def campaigns_root():
    return Path(__file__).resolve().parent / "campaigns"


def _require(condition, message):
    if not condition:
        raise CampaignError(message)


def _validateArtwork(data, where):
    if "artwork" not in data:
        return
    value = data["artwork"]
    _require(
        isinstance(value, str)
        and value.startswith("images/")
        and value.endswith(".png")
        and not any(part in value for part in ("..", "\\", ":")),
        f'{where}: "artwork" must be a PNG path inside images/',
    )


def artworkForMap(map_id):
    """Use only authored campaign artwork that is available in this resource tree."""
    try:
        for manifest in list_campaigns():
            for scenario in manifest["scenarios"].values():
                artwork = scenario.get("artwork", "")
                if scenario["map"] == map_id and artwork and (Path(__file__).resolve().parent / artwork).is_file():
                    return artwork
    except (CampaignError, OSError):
        pass
    return ""


def chapterCount(manifest):
    """Count chapters along reachable playthroughs, not mutually exclusive branches."""
    scenarios = manifest["scenarios"]
    # Older metadata-only callers provide summaries without route information.
    if any("next" not in scenario for scenario in scenarios.values()):
        return str(len(scenarios))
    memo = {}
    visiting = set()

    def depths(scenario_id):
        _require(scenario_id in scenarios, "chapter count: unknown scenario")
        _require(scenario_id not in visiting, "chapter count: campaign routes contain a cycle")
        if scenario_id in memo:
            return memo[scenario_id]
        visiting.add(scenario_id)
        routes = scenarios[scenario_id]["next"]
        children = [depths(target) for target in set(routes.values())]
        result = (
            (1 + min(child[0] for child in children), 1 + max(child[1] for child in children)) if children else (1, 1)
        )
        visiting.remove(scenario_id)
        memo[scenario_id] = result
        return result

    minimum, maximum = depths(manifest["start"])
    return str(minimum) if minimum == maximum else f"{minimum}-{maximum}"


# CampaignStateStore.record_outcome serializes history as
# "<scenario_id>:<outcome>" entries joined by ",". A scenario id or outcome key
# containing either delimiter would corrupt that string (mis-split ids/outcomes
# or fabricate entries), so reject them at validation time.
_HISTORY_DELIMITERS = (",", ":")


def _reject_history_delimiters(where, label, value):
    _require(
        not any(delimiter in value for delimiter in _HISTORY_DELIMITERS),
        f'{where}: {label} must not contain "," or ":" (reserved for campaign history)',
    )


def _validate_scenario(campaign_id, scenario_id, scenario, scenario_ids):
    where = f'campaign "{campaign_id}" scenario "{scenario_id}"'
    _reject_history_delimiters(where, f'scenario id "{scenario_id}"', scenario_id)
    _require(isinstance(scenario, dict), f"{where}: scenario must be an object")
    for key in SCENARIO_REQUIRED_KEYS:
        _require(key in scenario, f'{where}: missing required key "{key}"')
    for key in scenario:
        _require(key in SCENARIO_KEYS, f'{where}: unknown key "{key}"')
    for key in ("map", "title", "briefing"):
        value = scenario[key]
        _require(isinstance(value, str) and value, f'{where}: "{key}" must be a non-empty string')
    epilogue = scenario.get("epilogue", "")
    _require(isinstance(epilogue, str), f'{where}: "epilogue" must be a string')
    _validateArtwork(scenario, where)
    routes = scenario["next"]
    _require(isinstance(routes, dict), f'{where}: "next" must be an object mapping outcome to scenario id')
    for outcome, target in routes.items():
        _require(isinstance(outcome, str) and outcome, f'{where}: outcomes in "next" must be non-empty strings')
        _reject_history_delimiters(where, f'outcome "{outcome}"', outcome)
        _require(
            isinstance(target, str) and target in scenario_ids,
            f'{where}: "next" target for outcome "{outcome}" must name a scenario in this campaign',
        )
    _validate_carryover(where, scenario.get("carryover"))


def _validate_carryover(where, carryover):
    if carryover is None:
        return
    _require(isinstance(carryover, dict), f'{where}: "carryover" must be an object')
    for key in carryover:
        _require(key in CARRYOVER_KEYS, f'{where}: unknown carryover key "{key}"')
    _require(
        not (CARRYOVER_ITEMS_ALLOW in carryover and CARRYOVER_ITEMS_DENY in carryover),
        f'{where}: carryover may use "{CARRYOVER_ITEMS_ALLOW}" or "{CARRYOVER_ITEMS_DENY}", not both',
    )
    if CARRYOVER_GOLD_MAX in carryover:
        gold_max = carryover[CARRYOVER_GOLD_MAX]
        _require(
            isinstance(gold_max, int) and not isinstance(gold_max, bool) and gold_max >= 0,
            f'{where}: "{CARRYOVER_GOLD_MAX}" must be a non-negative integer',
        )
    for key in (CARRYOVER_ITEMS_ALLOW, CARRYOVER_ITEMS_DENY):
        if key not in carryover:
            continue
        items = carryover[key]
        _require(
            isinstance(items, list) and all(isinstance(item, str) and item for item in items),
            f'{where}: "{key}" must be a list of non-empty item ids',
        )


def validate_manifest(data):
    """Structural runtime validation; deep cross-content checks (map existence,
    outcome declarations, graph shape) live in scripts/validate_content.py."""
    _require(isinstance(data, dict), "campaign manifest must be a JSON object")
    for key in MANIFEST_REQUIRED_KEYS:
        _require(key in data, f'campaign manifest: missing required key "{key}"')
    for key in data:
        _require(key in MANIFEST_KEYS, f'campaign manifest: unknown key "{key}"')
    _require(data["format"] == CAMPAIGN_FORMAT, f'campaign manifest: "format" must be "{CAMPAIGN_FORMAT}"')
    _require(
        data["schemaVersion"] == CAMPAIGN_SCHEMA_VERSION,
        f'campaign manifest: "schemaVersion" must be {CAMPAIGN_SCHEMA_VERSION}',
    )
    campaign_id = data["campaignId"]
    _require(isinstance(campaign_id, str) and campaign_id, 'campaign manifest: "campaignId" must be a non-empty string')
    _require(isinstance(data["title"], str) and data["title"], 'campaign manifest: "title" must be a non-empty string')
    _validateArtwork(data, "campaign manifest")
    scenarios = data["scenarios"]
    _require(
        isinstance(scenarios, dict) and scenarios,
        f'campaign "{campaign_id}": "scenarios" must be a non-empty object',
    )
    start_id = data["start"]
    _require(
        isinstance(start_id, str) and start_id in scenarios,
        f'campaign "{campaign_id}": "start" must name a scenario in this campaign',
    )
    for scenario_id, scenario in scenarios.items():
        _validate_scenario(campaign_id, scenario_id, scenario, set(scenarios))
    return data


def load_manifest(manifest_path):
    path = Path(manifest_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CampaignError(f"cannot read campaign manifest {path}: {exc}") from exc
    return validate_manifest(data)


def list_campaigns(root=None):
    """Return every campaign manifest under ``root`` sorted by campaignId.

    Shipped content is gated by scripts/validate_content.py, so a broken
    manifest here is a content bug: it raises rather than being skipped.
    """
    root = campaigns_root() if root is None else Path(root)
    manifests = []
    if not root.is_dir():
        return manifests
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        manifest_path = directory / CAMPAIGN_MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        data = load_manifest(manifest_path)
        _require(
            data["campaignId"] == directory.name,
            f'campaign manifest {manifest_path}: "campaignId" must match its directory name "{directory.name}"',
        )
        manifests.append(data)
    return manifests


def get_manifest(campaign_id, root=None):
    # campaign_id can come from an untrusted save file (CampaignStateStore reads
    # it as a dynamic player property), so refuse anything but a bare directory
    # name to keep the manifest read inside campaigns_root().
    _require(
        isinstance(campaign_id, str)
        and campaign_id
        and "/" not in campaign_id
        and "\\" not in campaign_id
        and campaign_id not in (".", ".."),
        f"invalid campaign id {campaign_id!r}: must be a bare campaign directory name",
    )
    root = campaigns_root() if root is None else Path(root)
    manifest_path = root / campaign_id / CAMPAIGN_MANIFEST_NAME
    _require(manifest_path.is_file(), f'unknown campaign "{campaign_id}" (missing {manifest_path})')
    data = load_manifest(manifest_path)
    _require(
        data["campaignId"] == campaign_id,
        f'campaign manifest {manifest_path}: "campaignId" must match its directory name "{campaign_id}"',
    )
    return data


def next_scenario(manifest, scenario_id, outcome):
    """Route a reported scenario outcome. Returns the next scenario id, or
    ``None`` when the scenario is terminal (empty ``next``) and the campaign is
    complete. An outcome a non-terminal scenario does not route is a content
    bug (validate_content.py makes it unreachable for shipped content)."""
    scenarios = manifest["scenarios"]
    if scenario_id not in scenarios:
        raise CampaignError(f'campaign "{manifest["campaignId"]}" has no scenario "{scenario_id}"')
    routes = scenarios[scenario_id]["next"]
    if not routes:
        return None
    if outcome not in routes:
        raise CampaignError(
            f'campaign "{manifest["campaignId"]}" scenario "{scenario_id}" does not route outcome "{outcome}"'
        )
    return routes[outcome]


def apply_carryover(player, carryover):
    """Apply a scenario-entry carryover policy to the player. The default —
    no policy — carries everything, which is what the engine does naturally."""
    if not carryover:
        return
    if CARRYOVER_GOLD_MAX in carryover:
        gold_max = carryover[CARRYOVER_GOLD_MAX]
        gold = player.getGold()
        if gold > gold_max:
            player.addGold(gold_max - gold)
    if CARRYOVER_ITEMS_ALLOW in carryover:
        allowed = frozenset(carryover[CARRYOVER_ITEMS_ALLOW])
        _remove_inventory_items(player, lambda item: item.getTypeId() not in allowed)
    if CARRYOVER_ITEMS_DENY in carryover:
        denied = frozenset(carryover[CARRYOVER_ITEMS_DENY])
        _remove_inventory_items(player, lambda item: item.getTypeId() in denied)


def _carryoverPreview(player, policy):
    gold = min(player.getGold(), policy.get(CARRYOVER_GOLD_MAX, player.getGold()))
    allowed = policy.get(CARRYOVER_ITEMS_ALLOW)
    denied = policy.get(CARRYOVER_ITEMS_DENY, ())
    count = sum(
        1
        for item in player.getItems()
        if (allowed is None or item.getTypeId() in allowed) and item.getTypeId() not in denied
    )
    return gold, count


def _remove_inventory_items(player, predicate):
    match_count = sum(1 for item in player.getItems() if predicate(item))
    for _ in range(match_count):
        player.removeItem(predicate, True)


class CampaignStateStore:
    """Campaign position and cross-scenario variables, stored as dynamic
    properties on the player (mirroring quest_state.QuestStateStore, which
    stores per-map quest state on the map). The player crosses map transitions
    and serializes inside every save, so this state persists for free."""

    def __init__(self, player):
        self.player = player

    def campaign_id(self):
        return self.player.getStringProperty(CAMPAIGN_ID_PROPERTY)

    def scenario(self):
        return self.player.getStringProperty(CAMPAIGN_SCENARIO_PROPERTY)

    def finished(self):
        return self.player.getBoolProperty(CAMPAIGN_FINISHED_PROPERTY)

    def active(self):
        return bool(self.campaign_id()) and not self.finished()

    def begin(self, campaign_id, scenario_id):
        self.player.setStringProperty(CAMPAIGN_ID_PROPERTY, campaign_id)
        self.player.setStringProperty(CAMPAIGN_SCENARIO_PROPERTY, scenario_id)
        self.player.setStringProperty(CAMPAIGN_HISTORY_PROPERTY, "")
        self.player.setBoolProperty(CAMPAIGN_FINISHED_PROPERTY, False)

    def advance(self, scenario_id):
        self.player.setStringProperty(CAMPAIGN_SCENARIO_PROPERTY, scenario_id)

    def finish(self):
        self.player.setBoolProperty(CAMPAIGN_FINISHED_PROPERTY, True)

    def record_outcome(self, scenario_id, outcome):
        entry = f"{scenario_id}:{outcome}"
        history = self.player.getStringProperty(CAMPAIGN_HISTORY_PROPERTY)
        self.player.setStringProperty(CAMPAIGN_HISTORY_PROPERTY, f"{history},{entry}" if history else entry)

    def history(self):
        raw = self.player.getStringProperty(CAMPAIGN_HISTORY_PROPERTY)
        return [tuple(entry.split(":", 1)) for entry in raw.split(",") if entry]

    def set_var(self, name, value):
        _require(name.isidentifier(), f'campaign variable name "{name}" must be an identifier')
        self.player.setStringProperty(CAMPAIGN_VAR_PREFIX + name, str(value))

    def get_var(self, name, default=""):
        return self.player.getStringProperty(CAMPAIGN_VAR_PREFIX + name) or default


def state(game):
    """The CampaignStateStore for the current player, or None without one."""
    game_map = game.getMap()
    if game_map is None:
        return None
    player = game_map.getPlayer()
    if player is None:
        return None
    return CampaignStateStore(player)


def active(game):
    store = state(game)
    return store is not None and store.active()


def _show_message(game, text):
    if text:
        game.getGuiHandler().showMessage(text)


def _scenario_intro(scenario):
    return f'{scenario["title"]}. {scenario["briefing"]}'


ACTION_BEGIN = "Begin chapter"
ACTION_CONTINUE = "Continue"
ACTION_RETURN = "Return to adventure"


def _show_screen(game, title, body, action_label, fallback_text=None, artwork=""):
    """Show a blocking full-window campaign presentation screen.

    Uses CGuiHandler.showCampaignScreen when the GUI handler provides it (the
    engine's handler always does; headless runs log and return immediately).
    Pure-Python test doubles without the method fall back to the legacy
    showMessage flow so this module stays unit-testable without the engine.
    """
    if not body:
        return
    gui = game.getGuiHandler()
    show_artwork = getattr(gui, "showCampaignArtworkScreen", None)
    if artwork and callable(show_artwork):
        show_artwork(title, body, action_label, artwork)
        return
    show = getattr(gui, "showCampaignScreen", None)
    if callable(show):
        show(title, body, action_label)
        return
    _show_message(game, fallback_text if fallback_text is not None else body)


def _show_screenFlow(game, title, body, action_label, fallback_text=None, artwork=""):
    from ui import uiRequest

    if not body:
        return
    gui = game.getGuiHandler()
    if artwork and callable(getattr(gui, "showCampaignArtworkScreen", None)):
        yield uiRequest("gui.showCampaignArtworkScreen", title, body, action_label, artwork)
    elif callable(getattr(gui, "showCampaignScreen", None)):
        yield uiRequest("gui.showCampaignScreen", title, body, action_label)
    else:
        yield uiRequest("gui.showMessage", fallback_text if fallback_text is not None else body)


def start(game, campaign_id, player_class, race_id=""):
    from ui import runUiFlow

    return runUiFlow(game, startFlow(game, campaign_id, player_class, race_id))


def startFlow(game, campaign_id, player_class, race_id=""):
    """Begin a campaign: start its first scenario map with a fresh player of
    the given class/race, stamp campaign state onto that player, and show the
    opening briefing. Returns the campaign state store."""
    from ui import flowGame, uiRequest

    game = flowGame(game)

    manifest = get_manifest(campaign_id)
    first_id = manifest["start"]
    scenario = manifest["scenarios"][first_id]
    yield uiRequest("gui.startGameWithPlayer", scenario["map"], player_class, race_id)
    store = state(game)
    _require(store is not None, f'campaign "{campaign_id}" failed to start map "{scenario["map"]}" with a player')
    store.begin(campaign_id, first_id)
    yield uiRequest(
        "campaign._show_screen",
        game,
        scenario["title"],
        scenario["briefing"],
        ACTION_BEGIN,
        fallback_text=_scenario_intro(scenario),
        artwork=scenario.get("artwork", ""),
    )
    return store


def complete_scenario(game, outcome, fallback_map=None, outcome_summary=""):
    """Report the active scenario's outcome and let the manifest route it.

    Map scripts call this instead of hardcoding game.changeMap(next_map).
    With no active campaign (standalone map play) the legacy behavior is kept:
    the map changes to ``fallback_map`` when one is given, otherwise nothing
    happens. Optional outcome_summary describes rewards already committed by the
    caller and is included in the existing outcome acknowledgment. Returns the
    next scenario id, "" when the campaign finished, or None when no campaign was active.
    """
    from ui import runUiFlow

    return runUiFlow(game, complete_scenarioFlow(game, outcome, fallback_map, outcome_summary))


def prepareCompletion(game, outcome, fallback_map=None, outcome_summary=""):
    """Persist a committed authored outcome before its reward acknowledgment can be cancelled."""
    store = state(game)
    if store is None:
        return None
    pending = _pendingTransition(game)
    if pending and pending.get("stage") == "entry":
        _finalizeEntry(store, pending)
        pending = None
    if pending:
        _require(
            pending["scenario"] == store.scenario() and pending["outcome"] == outcome,
            "a different campaign outcome is already awaiting its map transition",
        )
        return pending
    if not store.active() and not fallback_map:
        return None
    target_id, target_map, stage = "", fallback_map or "", "authored"
    if store.active():
        manifest = get_manifest(store.campaign_id())
        target_id = next_scenario(manifest, store.scenario(), outcome)
        target_map = manifest["scenarios"][target_id]["map"] if target_id is not None else ""
        stage = "outcome"
    pending = {
        "campaignId": store.campaign_id(),
        "scenario": store.scenario(),
        "outcome": outcome,
        "targetMap": target_map,
        "targetScenario": target_id or "",
        "stage": stage,
        "outcomeSummary": outcome_summary,
    }
    map_name = getattr(game.getMap(), "getMapName", None)
    if callable(map_name):
        pending["sourceMap"] = map_name()
    store.player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, json.dumps(pending, sort_keys=True))
    return pending


def complete_scenarioFlow(game, outcome, fallback_map=None, outcome_summary=""):
    from ui import flowGame

    game = flowGame(game)
    pending = prepareCompletion(game, outcome, fallback_map, outcome_summary)
    if pending is None:
        if state(game) is None and fallback_map:
            game.changeMap(fallback_map)
        return None
    store = state(game)
    if pending.get("stage", "transition") in {"transition", "authored"}:
        _requestPendingTransition(game, pending)
        return pending["targetScenario"] if store.active() else None
    if _operationInFlight(game, _INFLIGHT_PRESENTATIONS):
        return pending["targetScenario"]
    guard = _TransitionGuard(game)
    _INFLIGHT_PRESENTATIONS[guard] = True
    try:
        return (yield from _presentCompletionFlow(game, store, pending))
    finally:
        _INFLIGHT_PRESENTATIONS.pop(guard, None)


def _presentCompletionFlow(game, store, pending):
    owner = _CompletionOwner(game, store)
    if not owner.isCurrent():
        return None
    manifest = get_manifest(pending["campaignId"])
    expected_id = next_scenario(manifest, pending["scenario"], pending["outcome"])
    _require(
        (expected_id or "") == pending["targetScenario"], "pending completion no longer matches the campaign route"
    )
    expected_map = manifest["scenarios"][expected_id]["map"] if expected_id is not None else ""
    _require(expected_map == pending["targetMap"], "pending completion map no longer matches its chapter")
    if pending["stage"] == "completion":
        _require(expected_id is None and store.finished(), "pending campaign completion was not committed")
        yield from _finishPresentationFlow(game, store, manifest)
        return ""
    if store.finished():
        _require(
            expected_id is None and (pending["scenario"], pending["outcome"]) in store.history(),
            "pending outcome conflicts with committed campaign completion",
        )
        pending["stage"] = "completion"
        store.player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, json.dumps(pending, sort_keys=True))
        yield from _finishPresentationFlow(game, store, manifest)
        return ""
    current_id = pending["scenario"]
    current = manifest["scenarios"][current_id]
    target_id = pending["targetScenario"] or None
    outcome = pending["outcome"]
    outcome_summary = pending.get("outcomeSummary", "")
    outcome_body = "Outcome: " + outcome.replace("_", " ").capitalize() + "."
    if current.get("epilogue"):
        outcome_body += "\n\n" + current["epilogue"]
    if outcome_summary:
        outcome_body += "\n\n" + outcome_summary
    if target_id is not None:
        outcome_body += "\n\nNext chapter: " + manifest["scenarios"][target_id]["title"]
    yield from _show_screenFlow(
        game,
        current["title"],
        outcome_body,
        ACTION_CONTINUE,
        fallback_text=outcome_body if outcome_summary else current.get("epilogue", outcome_body),
        artwork=current.get("artwork", ""),
    )
    if not owner.isCurrent():
        return None
    if target_id is None:
        if (current_id, outcome) not in store.history():
            store.record_outcome(current_id, outcome)
        store.finish()
        pending["stage"] = "completion"
        store.player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, json.dumps(pending, sort_keys=True))
        yield from _finishPresentationFlow(game, store, manifest)
        return ""
    pending["stage"] = "transition"
    store.player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, json.dumps(pending, sort_keys=True))
    _requestPendingTransition(game, pending)
    return target_id


def _finishPresentationFlow(game, store, manifest):
    owner = _CompletionOwner(game, store)
    yield from _show_screenFlow(
        game,
        manifest["title"],
        manifest.get("completionText") or f'The campaign "{manifest["title"]}" is complete.',
        ACTION_RETURN,
        artwork=manifest.get("artwork", ""),
    )
    if owner.isCurrent():
        store.player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, "")


def _pendingTransition(game):
    store = state(game)
    if store is None:
        return None
    raw = store.player.getStringProperty(CAMPAIGN_PENDING_PROPERTY)
    if not raw:
        return None
    try:
        pending = json.loads(raw)
        if not isinstance(pending, dict) or not all(
            isinstance(pending.get(key), str)
            for key in ("campaignId", "scenario", "outcome", "targetMap", "targetScenario")
        ):
            return None
        if pending["campaignId"] != store.campaign_id() or pending["scenario"] != store.scenario():
            return None
        if pending.get("stage", "transition") not in {"transition", "authored", "outcome", "completion", "entry"}:
            return None
        if not isinstance(pending.get("outcomeSummary", ""), str):
            return None
        if "sourceMap" in pending:
            map_name = getattr(game.getMap(), "getMapName", None)
            if (
                not isinstance(pending["sourceMap"], str)
                or not callable(map_name)
                or map_name() != pending["sourceMap"]
            ):
                return None
        return pending
    except (ValueError, TypeError):
        return None


def hasPendingTransition(game):
    """Whether a saved chapter outcome still needs acknowledgment or its map transition."""
    return _pendingTransition(game) is not None


def _beginTransition(game, store, outcome, target_map, target_id=""):
    pending = {
        "campaignId": store.campaign_id(),
        "scenario": store.scenario(),
        "outcome": outcome,
        "targetMap": target_map,
        "targetScenario": target_id,
    }
    store.player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, json.dumps(pending, sort_keys=True))
    return retryPending(game)


def retryPending(game):
    """Retry only the saved transition; authored rewards and judgments stay claimed."""
    from ui import runUiFlow

    return runUiFlow(game, retryPendingFlow(game))


def retryPendingFlow(game):
    from ui import flowGame, uiRequest

    game = flowGame(game)
    pending = _pendingTransition(game)
    if pending is None or _transitionInFlight(game) or _operationInFlight(game, _INFLIGHT_PRESENTATIONS):
        return False
    store = state(game)
    owner = _CompletionOwner(game, store)
    if pending.get("stage") == "entry":
        if not owner.isCurrent():
            return False
        _finalizeEntry(store, pending)
        if callable(getattr(store.player, "checkQuests", None)):
            yield uiRequest("gui.checkQuests", store.player)
        return True
    guard = _TransitionGuard(game)
    _INFLIGHT_PRESENTATIONS[guard] = True
    try:
        if pending.get("stage", "transition") in {"outcome", "authored"}:
            player = state(game).player
            if callable(getattr(player, "checkQuests", None)):
                yield uiRequest("gui.checkQuests", player)
                if not owner.isCurrent():
                    return False
        if pending.get("stage", "transition") in {"outcome", "completion"}:
            result = yield from _presentCompletionFlow(game, store, pending)
            return result is not None
        return _requestPendingTransition(game, pending)
    finally:
        _INFLIGHT_PRESENTATIONS.pop(guard, None)


def _finalizeEntry(store, pending):
    if pending["targetScenario"]:
        _require(
            (pending.get("sourceScenario", ""), pending["outcome"]) in store.history(),
            "pending destination entry has no committed outcome",
        )
    store.player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, "")


def _requestPendingTransition(game, pending):
    if _transitionInFlight(game):
        return False
    store = state(game)
    if store is None or _pendingTransition(game) != pending:
        return False
    owner = _CompletionOwner(game, store)
    if not owner.isCurrent():
        return False
    player = store.player
    source_scenario = pending["scenario"]
    owned_pending = owner.pending
    target = None
    if pending["targetScenario"]:
        manifest = get_manifest(pending["campaignId"])
        _require(
            next_scenario(manifest, pending["scenario"], pending["outcome"]) == pending["targetScenario"],
            "pending campaign transition no longer matches the campaign route",
        )
        target = manifest["scenarios"][pending["targetScenario"]]
        _require(target["map"] == pending["targetMap"], "pending campaign map no longer matches its chapter")
    original = None
    committed = False
    token = object()
    game = _callbackGame(game)
    guard = _TransitionGuard(game)
    _INFLIGHT_TRANSITIONS[guard] = token
    request_flow = getattr(game, "changeMapWithPreparationFlow", None)
    asynchronous = callable(request_flow)

    def beforeEntry():
        nonlocal original, committed
        _require(owner.isCurrent(check_generation=False), "The source adventure changed before chapter preparation")
        entry_owner = _CompletionOwner(game, store)
        original = (
            store.scenario(),
            player.getStringProperty(CAMPAIGN_HISTORY_PROPERTY),
            player.getGold(),
            set(player.getItems()),
        )
        if target is None:
            return
        briefing = target["briefing"]
        if target.get("carryover"):
            gold, count = _carryoverPreview(player, target["carryover"])
            briefing += f"\n\nCarryover\nGold carried: {gold}\nBag items carried: {count}"
            if CARRYOVER_GOLD_MAX in target["carryover"]:
                briefing += f"\nThis chapter limits carried gold to {target['carryover'][CARRYOVER_GOLD_MAX]}."

        def prepareFlow():
            yield from _show_screenFlow(
                game,
                target["title"],
                briefing,
                ACTION_BEGIN,
                fallback_text=_scenario_intro(target),
                artwork=target.get("artwork", ""),
            )
            _require(entry_owner.isCurrent(), "The source adventure changed during chapter preparation")

        return prepareFlow()

    def commitBeforeEntry():
        nonlocal committed, owned_pending
        _require(owner.isCurrent(check_generation=False), "The source adventure changed before chapter commit")
        if target is not None:
            apply_carryover(player, target.get("carryover"))
            if (source_scenario, pending["outcome"]) not in store.history():
                store.record_outcome(source_scenario, pending["outcome"])
            store.advance(pending["targetScenario"])
        committed = True
        pending["sourceScenario"] = source_scenario
        pending["scenario"] = store.scenario()
        pending["stage"] = "entry"
        if "sourceMap" in pending:
            pending["sourceMap"] = pending["targetMap"]
        owned_pending = json.dumps(pending, sort_keys=True)
        player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, owned_pending)

    def completion(success):
        if _INFLIGHT_TRANSITIONS.get(guard) is not token:
            return
        _INFLIGHT_TRANSITIONS.pop(guard, None)
        expected_scenario = pending["targetScenario"] if committed and target is not None else source_scenario
        owns_player = (
            store.campaign_id() == pending["campaignId"]
            and store.scenario() == expected_scenario
            and player.getStringProperty(CAMPAIGN_PENDING_PROPERTY) == owned_pending
        )
        if success:
            try:
                current = state(game)
                active = owner.context is None or owner.context.isActive()
                if (
                    owns_player
                    and active
                    and (target is None or committed)
                    and current is not None
                    and current.player is player
                ):
                    player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, "")
            except RuntimeError:
                pass
        else:
            can_restore = owns_player
            try:
                current_map = game.getMap()
                if current_map is not owner.map and current_map is not None and current_map.getPlayer() is player:
                    can_restore = False
            except RuntimeError:
                pass
            if original is not None and can_restore:
                scenario_id, history, gold, items = original
                store.advance(scenario_id)
                player.setStringProperty(CAMPAIGN_HISTORY_PROPERTY, history)
                player.addGold(gold - player.getGold())
                _remove_inventory_items(player, lambda item: item not in items)
                for item in items - set(player.getItems()):
                    player.addItem(item)
                player.setStringProperty(CAMPAIGN_PENDING_PROPERTY, owner.pending)
            if not owner.isCurrent(check_generation=False):
                return
            try:
                context = game.getContext() if hasattr(game, "getContext") else None
            except RuntimeError:
                return
            if context is None or context.isActive():
                message = (
                    "The next chapter could not be loaded. Your chapter progress and carried items "
                    "are unchanged. Retry the chapter transition from the pause menu."
                )
                if asynchronous:
                    game.getGuiHandler().showMessageLater(message)
                else:
                    _show_message(game, message)

    def beforeEntrySynchronous():
        from ui import runUiFlow

        presentation = beforeEntry()
        if presentation is not None:
            runUiFlow(game, presentation)
        commitBeforeEntry()

    def beforeEntryLegacyFlow():
        presentation = beforeEntry()
        if presentation is not None:
            yield from presentation
        commitBeforeEntry()

    try:
        if asynchronous:
            if _supportsCommitCallback(request_flow):
                return request_flow(pending["targetMap"], beforeEntry, completion, commitBeforeEntry)
            return request_flow(pending["targetMap"], beforeEntryLegacyFlow, completion)
        return game.changeMapWithPreparation(pending["targetMap"], beforeEntrySynchronous, completion)
    except Exception:
        # A binding error before the native request was queued must also release the retry lock.
        if _INFLIGHT_TRANSITIONS.get(guard) is token:
            completion(False)
        raise


def _supportsCommitCallback(callback):
    # Older Python adapters can preserve their synchronous preparation contract.
    # Native bindings must support the atomic fourth callback from this engine version.
    if not hasattr(callback, "__code__"):
        return True
    from inspect import Parameter, signature

    parameters = tuple(signature(callback).parameters.values())
    return (
        any(parameter.kind == Parameter.VAR_POSITIONAL for parameter in parameters)
        or sum(
            parameter.kind in {Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD} for parameter in parameters
        )
        >= 4
    )
