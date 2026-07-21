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

# Carryover policy keys supported at scenario entry. ``gold_max`` clamps gold,
# the item filters keep/strip inventory by config id. Exactly one of
# items_allow/items_deny may be present.
CARRYOVER_GOLD_MAX = "gold_max"
CARRYOVER_ITEMS_ALLOW = "items_allow"
CARRYOVER_ITEMS_DENY = "items_deny"
CARRYOVER_KEYS = (CARRYOVER_GOLD_MAX, CARRYOVER_ITEMS_ALLOW, CARRYOVER_ITEMS_DENY)

SCENARIO_REQUIRED_KEYS = ("map", "title", "briefing", "next")
SCENARIO_KEYS = ("map", "title", "briefing", "epilogue", "carryover", "next")
MANIFEST_REQUIRED_KEYS = ("format", "schemaVersion", "campaignId", "title", "start", "scenarios")
MANIFEST_KEYS = MANIFEST_REQUIRED_KEYS + ("description", "completionText")


class CampaignError(ValueError):
    """A campaign manifest or campaign runtime state is invalid."""


def campaigns_root():
    return Path(__file__).resolve().parent / "campaigns"


def _require(condition, message):
    if not condition:
        raise CampaignError(message)


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
        player.removeItem(lambda item: item.getName() not in allowed, True)
    if CARRYOVER_ITEMS_DENY in carryover:
        denied = frozenset(carryover[CARRYOVER_ITEMS_DENY])
        player.removeItem(lambda item: item.getName() in denied, True)


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


# Presentation-screen action labels, in required flow order: each briefing is
# dismissed with BEGIN, a scenario epilogue with CONTINUE, and the terminal
# campaign completion with RETURN.
ACTION_BEGIN = "BEGIN"
ACTION_CONTINUE = "CONTINUE"
ACTION_RETURN = "RETURN"


def _show_screen(game, title, body, action_label, fallback_text=None):
    """Show a blocking full-window campaign presentation screen.

    Uses CGuiHandler.showCampaignScreen when the GUI handler provides it (the
    engine's handler always does; headless runs log and return immediately).
    Pure-Python test doubles without the method fall back to the legacy
    showMessage flow so this module stays unit-testable without the engine.
    """
    if not body:
        return
    gui = game.getGuiHandler()
    show = getattr(gui, "showCampaignScreen", None)
    if callable(show):
        show(title, body, action_label)
        return
    _show_message(game, fallback_text if fallback_text is not None else body)


def start(game, campaign_id, player_class, race_id=""):
    """Begin a campaign: start its first scenario map with a fresh player of
    the given class/race, stamp campaign state onto that player, and show the
    opening briefing. Returns the campaign state store."""
    manifest = get_manifest(campaign_id)
    first_id = manifest["start"]
    scenario = manifest["scenarios"][first_id]
    from _game import CGameLoader  # lazy: keeps this module importable without the engine

    if race_id:
        CGameLoader.startGameWithPlayer(game, scenario["map"], player_class, race_id)
    else:
        CGameLoader.startGameWithPlayer(game, scenario["map"], player_class)
    store = state(game)
    _require(store is not None, f'campaign "{campaign_id}" failed to start map "{scenario["map"]}" with a player')
    store.begin(campaign_id, first_id)
    _show_screen(game, scenario["title"], scenario["briefing"], ACTION_BEGIN, fallback_text=_scenario_intro(scenario))
    return store


def complete_scenario(game, outcome, fallback_map=None):
    """Report the active scenario's outcome and let the manifest route it.

    Map scripts call this instead of hardcoding game.changeMap(next_map).
    With no active campaign (standalone map play) the legacy behavior is kept:
    the map changes to ``fallback_map`` when one is given, otherwise nothing
    happens. Returns the next scenario id, "" when the campaign finished, or
    None when no campaign was active.
    """
    store = state(game)
    if store is None or not store.active():
        if fallback_map:
            game.changeMap(fallback_map)
        return None
    manifest = get_manifest(store.campaign_id())
    current_id = store.scenario()
    current = manifest["scenarios"][current_id]
    target_id = next_scenario(manifest, current_id, outcome)
    store.record_outcome(current_id, outcome)
    _show_screen(game, current["title"], current.get("epilogue", ""), ACTION_CONTINUE)
    if target_id is None:
        store.finish()
        _show_screen(
            game,
            manifest["title"],
            manifest.get("completionText") or f'The campaign "{manifest["title"]}" is complete.',
            ACTION_RETURN,
        )
        return ""
    target = manifest["scenarios"][target_id]
    # Mutate the player before requesting the map change: the same player
    # object is re-attached to the destination map by CSceneManager.
    apply_carryover(game.getMap().getPlayer(), target.get("carryover"))
    store.advance(target_id)
    _show_screen(game, target["title"], target["briefing"], ACTION_BEGIN, fallback_text=_scenario_intro(target))
    game.changeMap(target["map"])
    return target_id
