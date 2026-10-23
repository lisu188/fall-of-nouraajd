/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025-2026  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include "CModuleBindings.h"
#include "core/CMap.h"
#include <pybind11/operators.h>
#include "core/CWrapper.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureClass.h"

namespace py = pybind11;

namespace nouraajd::bindings {
void bindGameplayObjects(py::module_ &m) {
    py::class_<CWaitState, CGameObject, std::shared_ptr<CWaitState>>(m, "CWaitState",
                                                                     "Serializable paused or running native wait.")
        .def(py::init<>())
        .def("getRemainingMilliseconds", &CWaitState::getRemainingMilliseconds)
        .def("setRemainingMilliseconds", [](CWaitState &state, const py::object &value) {
            if (!PyLong_CheckExact(value.ptr())) {
                throw py::type_error("Wait duration must be an integer number of milliseconds.");
            }
            const auto milliseconds = value.cast<long long>();
            if (milliseconds < 0 || milliseconds > CWaitState::MAX_MILLISECONDS) {
                throw py::value_error("Wait duration must be between 0 and 60000 milliseconds.");
            }
            state.setRemainingMilliseconds(static_cast<int>(milliseconds));
        });

    void (CMapObject::*moveTo)(int, int, int) = &CMapObject::moveTo;
    void (CMapObject::*move)(int, int, int) = &CMapObject::move;
    py::class_<CMapObject, CGameObject, std::shared_ptr<CMapObject>>(m, "CMapObject",
                                                                     "Base object that exists at map coordinates.")
        .def("getMap", &CMapObject::getMap, "Return the map containing this object.")
        .def("moveTo", moveTo, "Move this object to absolute coordinates.")
        .def("move", move, "Move this object by relative coordinate delta.")
        .def("relocateWithoutMoveHooks", &CMapObject::relocateWithoutMoveHooks,
             "Relocate this object without invoking movement hooks.")
        .def("getCoords", &CMapObject::getCoords, "Return current map coordinates.")
        .def("setCoords", &CMapObject::setCoords, "Set map coordinates.");

    auto cbuilding = py::class_<CBuilding, CWrapper<CBuilding>, std::shared_ptr<CBuilding>, CMapObject>(
        m, "CBuilding", "Base building object class.");
    cbuilding.def(py::init_alias<>())
        .def("onCreate", &CBuilding::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CBuilding::onTurn, "Handle onTurn game event.")
        .def("onDestroy", &CBuilding::onDestroy, "Handle onDestroy game event.")
        .def("onLeave", &CBuilding::onLeave, "Handle onLeave game event.")
        .def("onEnter", &CBuilding::onEnter, "Handle onEnter game event.");
    m.attr("CBuildingBase") = cbuilding;

    auto cevent = py::class_<CEvent, CWrapper<CEvent>, std::shared_ptr<CEvent>, CMapObject>(
        m, "CEvent", "Base map event object class.");
    cevent.def(py::init_alias<>())
        .def("onCreate", &CEvent::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CEvent::onTurn, "Handle onTurn game event.")
        .def("onLeave", &CEvent::onLeave, "Handle onLeave game event.")
        .def("onDestroy", &CEvent::onDestroy, "Handle onDestroy game event.")
        .def("onEnter", &CEvent::onEnter, "Handle onEnter game event.");
    m.attr("CEventBase") = cevent;

    auto cinteraction =
        py::class_<CInteraction, CWrapper<CInteraction>, std::shared_ptr<CInteraction>, CGameObject>(
            m, "CInteraction", "Base interaction/action definition.")
            .def(py::init_alias<>())
            .def("onAction", &CInteraction::onAction, "Engine callback when the interaction is activated.");
    cinteraction
        .def("performAction", &CInteraction::performAction,
             "Perform the interaction between source and target creatures.")
        .def("configureEffect", &CInteraction::configureEffect, "Configure an effect instance before it is applied.")
        .def("getCommittedManaRefund", &CInteraction::getCommittedManaRefund, py::arg("caster"),
             "Query the mana refund after a fully paid cast; querying never restores mana.");
    m.attr("CInteractionBase") = cinteraction;

    py::class_<StatsModifier>(m, "StatsModifier", "Pure numeric stat modifier value.")
        .def(py::init<>())
        .def_readwrite("strength", &StatsModifier::strength)
        .def_readwrite("agility", &StatsModifier::agility)
        .def_readwrite("stamina", &StatsModifier::stamina)
        .def_readwrite("intelligence", &StatsModifier::intelligence)
        .def_readwrite("armor", &StatsModifier::armor)
        .def_readwrite("block", &StatsModifier::block)
        .def_readwrite("dmgMin", &StatsModifier::dmgMin)
        .def_readwrite("dmgMax", &StatsModifier::dmgMax)
        .def_readwrite("attack", &StatsModifier::attack)
        .def_readwrite("hit", &StatsModifier::hit)
        .def_readwrite("crit", &StatsModifier::crit)
        .def_readwrite("fireResist", &StatsModifier::fireResist)
        .def_readwrite("frostResist", &StatsModifier::frostResist)
        .def_readwrite("normalResist", &StatsModifier::normalResist)
        .def_readwrite("thunderResist", &StatsModifier::thunderResist)
        .def_readwrite("shadowResist", &StatsModifier::shadowResist)
        .def_readwrite("damage", &StatsModifier::damage)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(-py::self);

    py::class_<DamageValue>(m, "DamageValue", "Pure typed damage value.")
        .def(py::init<>())
        .def_readwrite("normal", &DamageValue::normal)
        .def_readwrite("fire", &DamageValue::fire)
        .def_readwrite("frost", &DamageValue::frost)
        .def_readwrite("thunder", &DamageValue::thunder)
        .def_readwrite("shadow", &DamageValue::shadow)
        .def("scale", &DamageValue::scale, py::return_value_policy::reference_internal)
        .def("scaled", &DamageValue::scaled)
        .def(py::self == py::self)
        .def(py::self != py::self)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(-py::self);

    py::class_<CDamage, CGameObject, std::shared_ptr<CDamage>>(m, "CDamage",
                                                               "CDamage packet with typed damage components.")
        .def("getNormal", &CDamage::getNormal, "Return normal damage.")
        .def("setNormal", &CDamage::setNormal, "Set normal damage.")
        .def("getFire", &CDamage::getFire, "Return fire damage.")
        .def("setFire", &CDamage::setFire, "Set fire damage.")
        .def("getFrost", &CDamage::getFrost, "Return frost damage.")
        .def("setFrost", &CDamage::setFrost, "Set frost damage.")
        .def("getThunder", &CDamage::getThunder, "Return thunder damage.")
        .def("setThunder", &CDamage::setThunder, "Set thunder damage.")
        .def("getShadow", &CDamage::getShadow, "Return shadow damage.")
        .def("setShadow", &CDamage::setShadow, "Set shadow damage.")
        .def("value", &CDamage::value, "Return this packet as a pure DamageValue.")
        .def("apply", &CDamage::apply, py::return_value_policy::reference_internal,
             "Add a pure DamageValue to this packet.")
        .def(
            "__iadd__", [](CDamage &self, const CDamage &other) -> CDamage & { return self += other; },
            py::return_value_policy::reference_internal);

    py::class_<CStats, CGameObject, std::shared_ptr<CStats>>(m, "CStats",
                                                             "Creature stat container used for combat calculations.")
        .def("setStrength", &CStats::setStrength, "Set strength.")
        .def("setAgility", &CStats::setAgility, "Set agility.")
        .def("setStamina", &CStats::setStamina, "Set stamina.")
        .def("setIntelligence", &CStats::setIntelligence, "Set intelligence.")
        .def("setArmor", &CStats::setArmor, "Set armor reduction percentage.")
        .def("setBlock", &CStats::setBlock, "Set block chance percentage.")
        .def("setDmgMin", &CStats::setDmgMin, "Set minimum base damage.")
        .def("setDmgMax", &CStats::setDmgMax, "Set maximum base damage.")
        .def("setHit", &CStats::setHit, "Set hit chance modifier.")
        .def("setCrit", &CStats::setCrit, "Set critical chance percentage.")
        .def("getStrength", &CStats::getStrength, "Return strength.")
        .def("getAgility", &CStats::getAgility, "Return agility.")
        .def("getStamina", &CStats::getStamina, "Return stamina.")
        .def("getIntelligence", &CStats::getIntelligence, "Return intelligence.")
        .def("getMainValue", &CStats::getMainValue, "Return current value of the configured main stat.")
        .def("modifier", &CStats::modifier, "Return numeric stats as a pure StatsModifier.")
        .def("apply", &CStats::apply, py::return_value_policy::reference_internal,
             "Add a pure StatsModifier to this stat container.")
        .def(
            "__iadd__", [](CStats &self, const CStats &other) -> CStats & { return self += other; },
            py::return_value_policy::reference_internal)
        .def(
            "__isub__", [](CStats &self, const CStats &other) -> CStats & { return self -= other; },
            py::return_value_policy::reference_internal)
        .def("addBonus", &CStats::addBonus, "Add all numeric stats from another CStats object.")
        .def("removeBonus", &CStats::removeBonus, "Remove all numeric stats from another CStats object.")
        .def("getText", &CStats::getText, "Return formatted stat summary text.");

    py::class_<CCreatureRace, CGameObject, std::shared_ptr<CCreatureRace>>(
        m, "CCreatureRace", "Creature race archetype definition (metadata only; not a spawnable creature).")
        .def(py::init<>())
        .def("getBaseStats", &CCreatureRace::getBaseStats, "Return the race's innate base stats.")
        .def("setBaseStats", &CCreatureRace::setBaseStats, "Set the race's innate base stats (null becomes empty).")
        .def("getActions", &CCreatureRace::getActions, "Return the race's innate actions.")
        .def("setActions", &CCreatureRace::setActions, "Set the race's innate actions (nulls are dropped).")
        .def("getCreatureType", &CCreatureRace::getCreatureType, "Return the coarse creature type string.")
        .def("setCreatureType", &CCreatureRace::setCreatureType, "Set the coarse creature type string.")
        .def("getSubtypes", &CCreatureRace::getSubtypes, "Return the race's subtype tags.")
        .def("setSubtypes", &CCreatureRace::setSubtypes, "Set the race's subtype tags.")
        .def("isPlayerSelectable", &CCreatureRace::isPlayerSelectable,
             "Whether the race is offered at character creation.")
        .def("setPlayerSelectable", &CCreatureRace::setPlayerSelectable, "Set whether the race is player-selectable.")
        .def("getAssociatedClasses", &CCreatureRace::getAssociatedClasses,
             "Return the class ids that reinforce this race's natural role (future encounter-balance metadata).")
        .def("setAssociatedClasses", &CCreatureRace::setAssociatedClasses,
             "Set the associated class ids (empty ids are dropped).")
        .def("isAssociatedClass", py::overload_cast<const std::string &>(&CCreatureRace::isAssociatedClass),
             "Whether the class id is listed as reinforcing this race's natural role.");

    py::class_<CCreatureClass, CGameObject, std::shared_ptr<CCreatureClass>>(
        m, "CCreatureClass", "Creature class archetype definition (metadata only; not a spawnable creature).")
        .def(py::init<>())
        .def("getBaseStats", &CCreatureClass::getBaseStats, "Return the class's base stats.")
        .def("setBaseStats", &CCreatureClass::setBaseStats, "Set the class's base stats (null becomes empty).")
        .def("getLevelStats", &CCreatureClass::getLevelStats, "Return the class's per-level stat growth.")
        .def("setLevelStats", &CCreatureClass::setLevelStats,
             "Set the class's per-level stat growth (null becomes empty).")
        .def("getActions", &CCreatureClass::getActions, "Return the class's starting actions.")
        .def("setActions", &CCreatureClass::setActions, "Set the class's starting actions (nulls are dropped).")
        .def("getLevelling", &CCreatureClass::getLevelling, "Return the level-keyed unlock map.")
        .def("setLevelling", &CCreatureClass::setLevelling,
             "Set the level-keyed unlock map (null entries are dropped).")
        .def("getMainStat", &CCreatureClass::getMainStat, "Return the name of the class's main stat.")
        .def("setMainStat", &CCreatureClass::setMainStat, "Set the name of the class's main stat.");

    auto ctile =
        py::class_<CTile, CWrapper<CTile>, std::shared_ptr<CTile>, CGameObject>(m, "CTile", "Base tile class.");
    ctile.def(py::init_alias<>())
        .def("onStep", &CTile::onStep, "Handle a creature stepping on this tile.")
        .def("getMovementCost", &CTile::getMovementCost, "Return this tile's pathfinding movement cost.")
        .def("setMovementCost", &CTile::setMovementCost, "Set this tile's pathfinding movement cost.")
        .def("getTileType", &CTile::getTileType, "Return this tile's terrain type.");
    m.attr("CTileBase") = ctile;

    py::class_<CItem, CMapObject, std::shared_ptr<CItem>>(m, "CItem", "Base inventory/equipment item.")
        .def("getPower", &CItem::getPower, "Return the item power/price tier.")
        .def("getCoveredSlots", &CItem::getCoveredSlots,
             "Return the extra equipment slot ids this item occupies while equipped (empty for normal items).");
    auto cpotion = py::class_<CPotion, CWrapper<CPotion>, std::shared_ptr<CPotion>, CItem>(m, "CPotion",
                                                                                           "Base potion item class.");
    cpotion.def(py::init_alias<>()).def("onUse", &CPotion::onUse, "Handle potion use event.");
    m.attr("CPotionBase") = cpotion;
    auto cscroll = py::class_<CScroll, CWrapper<CScroll>, std::shared_ptr<CScroll>, CItem>(m, "CScroll",
                                                                                           "Base scroll item class.");
    cscroll.def(py::init_alias<>())
        .def("onUse", &CScroll::onUse, "Handle scroll use event.")
        .def("isDisposable", &CScroll::isDisposable, "Return whether the scroll is consumed on use.");
    m.attr("CScrollBase") = cscroll;

    // Equipment slot base classes, exposed with the CWrapper trampoline + init_alias so
    // Python content plugins can subclass them (e.g. compound-artifact set pieces and
    // combined artifacts in res/plugins/artifact_sets.py). Their onEquip/onUnequip/onUse
    // handlers dispatch to Python overrides via CPythonOverrides (see CItem.cpp).
    py::class_<CArmor, CWrapper<CArmor>, std::shared_ptr<CArmor>, CItem>(m, "CArmor", "Base body-armor item class.")
        .def(py::init_alias<>())
        .def("onEquip", &CArmor::onEquip, "Handle equip event.")
        .def("onUnequip", &CArmor::onUnequip, "Handle unequip event.")
        .def("onUse", &CArmor::onUse, "Handle use event.");
    py::class_<CHelmet, CWrapper<CHelmet>, std::shared_ptr<CHelmet>, CItem>(m, "CHelmet", "Base helmet item class.")
        .def(py::init_alias<>())
        .def("onEquip", &CHelmet::onEquip, "Handle equip event.")
        .def("onUnequip", &CHelmet::onUnequip, "Handle unequip event.")
        .def("onUse", &CHelmet::onUse, "Handle use event.");
    py::class_<CBoots, CWrapper<CBoots>, std::shared_ptr<CBoots>, CItem>(m, "CBoots", "Base boots item class.")
        .def(py::init_alias<>())
        .def("onEquip", &CBoots::onEquip, "Handle equip event.")
        .def("onUnequip", &CBoots::onUnequip, "Handle unequip event.")
        .def("onUse", &CBoots::onUse, "Handle use event.");
    py::class_<CGloves, CWrapper<CGloves>, std::shared_ptr<CGloves>, CItem>(m, "CGloves", "Base gloves item class.")
        .def(py::init_alias<>())
        .def("onEquip", &CGloves::onEquip, "Handle equip event.")
        .def("onUnequip", &CGloves::onUnequip, "Handle unequip event.")
        .def("onUse", &CGloves::onUse, "Handle use event.");
    py::class_<CBelt, CWrapper<CBelt>, std::shared_ptr<CBelt>, CItem>(m, "CBelt", "Base belt item class.")
        .def(py::init_alias<>())
        .def("onEquip", &CBelt::onEquip, "Handle equip event.")
        .def("onUnequip", &CBelt::onUnequip, "Handle unequip event.")
        .def("onUse", &CBelt::onUse, "Handle use event.");
    py::class_<CShield, CWrapper<CShield>, std::shared_ptr<CShield>, CItem>(m, "CShield", "Base shield item class.")
        .def(py::init_alias<>())
        .def("onEquip", &CShield::onEquip, "Handle equip event.")
        .def("onUnequip", &CShield::onUnequip, "Handle unequip event.")
        .def("onUse", &CShield::onUse, "Handle use event.");
    py::class_<CPants, CWrapper<CPants>, std::shared_ptr<CPants>, CItem>(m, "CPants", "Base leg-armor item class.")
        .def(py::init_alias<>())
        .def("onEquip", &CPants::onEquip, "Handle equip event.")
        .def("onUnequip", &CPants::onUnequip, "Handle unequip event.")
        .def("onUse", &CPants::onUse, "Handle use event.");

    py::class_<CGameEvent, CGameObject, std::shared_ptr<CGameEvent>>(m, "CGameEvent", "Base event object.");
    py::class_<CGameEventCaused, CGameEvent, std::shared_ptr<CGameEventCaused>>(m, "CGameEventCaused",
                                                                                "Event carrying a causing game object.")
        .def("getCause", &CGameEventCaused::getCause, "Return the object that caused this event.");

    auto ctrigger = py::class_<CTrigger, CWrapper<CTrigger>, std::shared_ptr<CTrigger>, CGameObject>(
        m, "CTrigger", "Base trigger class.");
    ctrigger.def(py::init_alias<>())
        .def("trigger", &CTrigger::trigger, "Handle trigger execution for an object and event.");
    m.attr("CTriggerBase") = ctrigger;

    auto cquest =
        py::class_<CQuest, CWrapper<CQuest>, std::shared_ptr<CQuest>, CGameObject>(m, "CQuest", "Base quest class.");
    cquest.def(py::init_alias<>())
        .def("isCompleted", &CQuest::isCompleted, "Return whether quest objectives are completed.")
        .def("onComplete", &CQuest::onComplete, "Handle quest completion callback.")
        .def("captureJournal", &CQuest::captureJournal, py::arg("completed"),
             "Capture quest journal state for completion, saving, or leaving its map.")
        .def("getObjective", &CQuest::getObjective, "Return current quest objective text.")
        .def("getReward", &CQuest::getReward, "Return quest reward text.")
        .def("getHint", &CQuest::getHint, "Return optional quest hint text.");
    m.attr("CQuestBase") = cquest;

    auto cdialog = py::class_<CDialog, CWrapper<CDialog>, std::shared_ptr<CDialog>, CGameObject>(
        m, "CDialog", "Base dialog definition.");
    cdialog.def(py::init_alias<>())
        .def("invokeAction", &CDialog::invokeAction, "Run a named dialog action callback.")
        .def("invokeCondition", &CDialog::invokeCondition, "Evaluate a named dialog condition callback.")
        .def("getStates", &CDialog::getStates, "Return dialog states.")
        .def("setStates", &CDialog::setStates, "Replace dialog states.");
    m.attr("CDialogBase") = cdialog;
    m.attr("CDialogBase2") = cdialog;

    py::class_<CDialogOption, CGameObject, std::shared_ptr<CDialogOption>>(m, "CDialogOption",
                                                                           "Single selectable dialog option.");
    py::class_<CDialogState, CGameObject, std::shared_ptr<CDialogState>>(m, "CDialogState", "Dialog state node.")
        .def("getOptions", &CDialogState::getOptions, "Return dialog options.")
        .def("setOptions", &CDialogState::setOptions, "Replace dialog options.");
}
} // namespace nouraajd::bindings
