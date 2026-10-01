"""Bounded consequences for the existing Nouraajd campaign chapters."""

import campaign

CLASS_DEEDS = {
    "Warrior": ("braced_nouraajd_gate", "bracedGate", "Your repaired gate braces gave the watch time to regroup."),
    "Assasin": (
        "shadowed_robed_men",
        "shadowedCultists",
        "Your courtyard trail helped the watch identify cult runners.",
    ),
    "Sorcerer": (
        "decoded_stained_glass_ward",
        "decodedWard",
        "Your reading of the glass ward reached the chapel witness.",
    ),
    "Inquisitor": (
        "inspected_stained_glass",
        "readCultSeal",
        "Your record of the cult seal reached the chapel witness.",
    ),
    "Wayfarer": ("charted_smuggler_route", "chartedRoute", "Your marsh chart helped refugees reach the gatehouse."),
}


def getVariable(game, name, default=""):
    store = campaign.state(game)
    return store.get_var(name, default) if store else default


def _recordFirstChoice(game, name, value):
    store = campaign.state(game)
    if store and not store.get_var(name):
        store.set_var(name, value)


def recordGateApproach(game, approach):
    if approach not in ("cooperative", "threatened"):
        raise ValueError("Unknown gate approach")
    _recordFirstChoice(game, "nouraajdGateApproach", approach)


def recordVictorConfrontation(game, approach):
    if approach not in ("forceful", "deescalated"):
        raise ValueError("Unknown Victor confrontation")
    _recordFirstChoice(game, "nouraajdVictorConfrontation", approach)


def snapshotTown(game, victor_state):
    store = campaign.state(game)
    if not store:
        return
    outcome = {"good_end": "rescued", "bad_end": "lost", "not_started": "notAttempted"}.get(victor_state, "unresolved")
    store.set_var("nouraajdVictorOutcome", outcome)
    player = store.player
    deed = CLASS_DEEDS.get(player.getPlayerClassId())
    store.set_var("nouraajdClassDeed", deed[1] if deed and player.getBoolProperty(deed[0]) else "none")


def beerSalePercent(game):
    return 105 if getVariable(game, "nouraajdGateApproach") == "threatened" else 100


def siegeRewardGold(game):
    return 475 if getVariable(game, "nouraajdGateApproach") == "threatened" else 500


def victorResponse(game):
    approach = getVariable(game, "nouraajdVictorConfrontation")
    if approach == "forceful":
        return "Victor remembers the blow you struck in the inn; he keeps his distance."
    if approach == "deescalated":
        return "Victor remembers that you listened before offering your blade."
    return ""


def townRecap(game):
    lines = []
    approach = getVariable(game, "nouraajdGateApproach")
    if approach == "threatened":
        lines.append(
            "The watch remembers your threat at the town gate. The gatehouse keeps 25 gold of its bounty for repairs."
        )
    elif approach == "cooperative":
        lines.append("The watch remembers your pledge at the town gate and trusts your warning.")
    response = victorResponse(game)
    if response:
        lines.append(response)
    outcome = getVariable(game, "nouraajdVictorOutcome", "notAttempted")
    if outcome == "rescued":
        lines.append("Victor and his daughter joined the refugees on the marsh road.")
    elif outcome == "lost":
        lines.append("Victor's daughter was lost; the chapel witness has heard his warning about the cult.")
    elif outcome == "unresolved":
        lines.append("Victor's search remained unfinished when you left town.")
    deed = getVariable(game, "nouraajdClassDeed", "none")
    for _, deed_id, text in CLASS_DEEDS.values():
        if deed == deed_id:
            lines.append(text)
            break
    return "\n\n".join(lines)


def recordRitualOutcome(game, outcome):
    if outcome not in ("good", "bad"):
        raise ValueError("Unknown ritual outcome")
    _recordFirstChoice(game, "ritualOutcome", outcome)


def ritualSummary(game):
    outcome = getVariable(game, "ritualOutcome")
    if outcome == "good":
        return "The rescued captive brought the chapel's warning to the gatehouse. A life was saved before the glass went dark."
    if outcome == "bad":
        return "You ended the rite after the captive was lost. The gatehouse hears your warning, and keeps a place for the missing."
    return ""


def siegeSummary(game):
    return "\n\n".join(text for text in (ritualSummary(game), townRecap(game)) if text)


def appendDialogContext(dialog, state_id, text):
    if not text or dialog.getBoolProperty("narrativeContextApplied"):
        return
    for state in dialog.getStates():
        if state.getStringProperty("stateId") == state_id:
            state.setStringProperty("text", state.getStringProperty("text") + "\n\n" + text)
            dialog.setBoolProperty("narrativeContextApplied", True)
            return
