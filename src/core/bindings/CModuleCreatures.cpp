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
#include "core/CController.h"
#include "handler/CEventHandler.h"
#include "core/CList.h"
#include "core/CWrapper.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureClass.h"

namespace py = pybind11;

namespace nouraajd::bindings {
void bindCreatures(py::module_ &m) {
    auto ceffect = py::class_<CEffect, CWrapper<CEffect>, std::shared_ptr<CEffect>, CGameObject>(
                       m, "CEffect", "Base status effect class.")
                       .def(py::init_alias<>())
                       .def("apply", &CEffect::apply, "Apply one effect tick to the given creature.")
                       .def("getBonus", &CEffect::getBonus, "Return effect stat bonus object.")
                       .def("setBonus", &CEffect::setBonus, "Set effect stat bonus object.")
                       .def("getCaster", &CEffect::getCaster, "Return creature that applied the effect.")
                       .def("setCaster", &CEffect::setCaster, "Set the creature that applied this effect.")
                       .def("getVictim", &CEffect::getVictim, "Return creature affected by the effect.")
                       .def("setVictim", &CEffect::setVictim, "Set the creature affected by this effect.")
                       .def("getTimeLeft", &CEffect::getTimeLeft, "Return remaining effect duration in turns.")
                       .def("onEffect", &CEffect::onEffect, "Apply effect behavior for one tick.");
    m.attr("CEffectBase") = ceffect;

    py::class_<CWeapon, CWrapper<CWeapon>, std::shared_ptr<CWeapon>, CItem>(m, "CWeapon", "Weapon item.")
        .def(py::init_alias<>())
        .def("getInteraction", &CWeapon::getInteraction, "Return interaction used when this weapon is applied.")
        .def("onEquip", &CWeapon::onEquip, "Handle equip event.")
        .def("onUnequip", &CWeapon::onUnequip, "Handle unequip event.")
        .def("onUse", &CWeapon::onUse, "Handle use event.");
    py::class_<CSmallWeapon, CWrapper<CSmallWeapon>, std::shared_ptr<CSmallWeapon>, CWeapon>(
        m, "CSmallWeapon", "Off-hand small weapon item.")
        .def(py::init_alias<>());

    void (CCreature::*hurtInt)(int) = &CCreature::hurt;
    void (CCreature::*hurtFloat)(float) = &CCreature::hurt;
    void (CCreature::*hurtDmg)(std::shared_ptr<CDamage>) = &CCreature::hurt;
    void (CCreature::*addItemByName)(std::string) = &CCreature::addItem;
    void (CCreature::*addItemByObject)(std::shared_ptr<CItem>) = &CCreature::addItem;
    bool (CCreature::*hasItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::hasItem;
    void (CCreature::*removeItem)(std::function<bool(std::shared_ptr<CItem>)>, bool) = &CCreature::removeItem;
    void (CCreature::*removeQuestItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::removeQuestItem;
    py::class_<CCreature, CMapObject, std::shared_ptr<CCreature>>(
        m, "CCreature", "Creature that can move, fight, and manage inventory.")
        .def("getDmg", &CCreature::getDmg, py::arg("allowCrit") = true, "Roll outgoing attack damage.")
        .def("hurt", hurtInt, "Apply raw damage value (int).")
        .def("hurt", hurtDmg, "Apply structured CDamage object.")
        .def("hurt", hurtFloat, "Apply damage value (float), rounded to int.")
        .def("getWeapon", &CCreature::getWeapon, "Return equipped weapon or None.")
        .def("getItemAtSlot", &CCreature::getItemAtSlot, "Return the item equipped in the given slot, or None.")
        .def("equipItem", &CCreature::equipItem, py::arg("slot"), py::arg("item"),
             "Equip an item into the given slot; pass None to unequip whatever is there.")
        .def("getEquipped", &CCreature::getEquipped, "Return a {slot id: item} map of currently equipped items.")
        .def("getSlotWithItem", &CCreature::getSlotWithItem,
             "Return the slot id holding the given item, or empty string if not equipped.")
        .def("hasEquipped", static_cast<bool (CCreature::*)(std::shared_ptr<CItem>)>(&CCreature::hasEquipped),
             "Return whether the given item is currently equipped.")
        .def(
            "unequipArmor", [](CCreature &creature) { creature.setArmor(nullptr); }, "Unequip current armor item.")
        .def("getHpRatio", &CCreature::getHpRatio, "Return HP percentage (0-100).")
        .def("isAlive", &CCreature::isAlive, "Return whether HP is above zero.")
        .def("getMana", &CCreature::getMana, "Return current mana.")
        .def("getManaMax", &CCreature::getManaMax, "Return maximum mana.")
        .def("healProc", &CCreature::healProc, "Restore HP by percentage of max HP.")
        .def("heal", &CCreature::heal, "Restore HP by fixed amount (0 means full heal).")
        .def("getHpMax", &CCreature::getHpMax, "Return maximum HP.")
        .def("getLevel", &CCreature::getLevel, "Return level.")
        .def("getStats", &CCreature::getStats, "Return aggregated combat stats.")
        .def("addManaProc", &CCreature::addManaProc, "Restore mana by percentage of max mana.")
        .def("addMana", &CCreature::addMana, py::arg("amount"),
             "Restore an absolute amount of mana, clamped to maximum; zero restores mana fully.")
        .def("isPlayer", &CCreature::isPlayer, "Return whether this creature is the active player.")
        .def("isNpc", &CCreature::isNpc, "Return whether this creature is marked as NPC.")
        .def("getController", &CCreature::getController, "Return the movement controller.")
        .def("setController", &CCreature::setController, "Set the movement controller.")
        .def("getFightController", &CCreature::getFightController, "Return the fight controller.")
        .def("setFightController", &CCreature::setFightController, "Set the fight controller.")
        .def("getHp", &CCreature::getHp, "Return current HP.")
        .def("setHp", &CCreature::setHp, "Set current HP.")
        .def("setMana", &CCreature::setMana, "Set current mana.")
        .def("addExp", &CCreature::addExp, "Add experience and trigger level ups when thresholds are reached.")
        .def("getGold", &CCreature::getGold, "Return current gold.")
        .def("addGold", &CCreature::addGold, "Add gold to the creature inventory.")
        .def("takeGold", &CCreature::takeGold, "Remove gold from the creature inventory.")
        .def("takeMana", &CCreature::takeMana, "Consume mana, clamped at zero.")
        .def("useAction", &CCreature::useAction, "Use an interaction/action against another creature.")
        .def("useItem", &CCreature::useItem, "Use an inventory item if it is currently usable.")
        .def("hasItem", hasItem, "Return whether any inventory item matches predicate(item) -> bool.")
        .def("addItem", addItemByName, "Create and add an item by type id.")
        .def("addItem", addItemByObject, "Add an existing item object.")
        .def("addItems", &CCreature::addItems, "Add all items from a set to inventory.")
        .def("setItems", &CCreature::setItems, "Replace inventory items.")
        .def("getItems", &CCreature::getItems, "Return inventory items.")
        .def("addEffect", &CCreature::addEffect, "Add one active effect while retaining existing effects and tracking.")
        .def("setEffects", &CCreature::setEffects, "Replace active effects.")
        .def("getEffects", &CCreature::getEffects, "Return active effects.")
        .def("getActions", &CCreature::getActions, "Return available actions.")
        .def("addAction", &CCreature::addAction, "Add an interaction to this creature's own action set.")
        .def("getEffectiveInteractions", &CCreature::getEffectiveInteractions,
             "Return the composed effective action set (race, class, level unlocks and own actions).")
        .def("removeItem", removeItem,
             "Remove the first inventory item matching predicate(item). Optional second arg allows quest removal.")
        .def("removeQuestItem", removeQuestItem, "Remove first matching quest item predicate from inventory.")
        .def("countItems", &CCreature::countItems, "Count inventory items by type id.")
        .def("getArchetypeRaceId", &CCreature::getArchetypeRaceId,
             "Return the creature archetype race identity id (configured type id, falling back to name).")
        .def("getArchetypeClassId", &CCreature::getArchetypeClassId,
             "Return the creature archetype class identity id (configured type id, falling back to name).")
        .def("getArchetypeRaceLabel", &CCreature::getArchetypeRaceLabel,
             "Return the creature archetype race display label (label, falling back to the archetype race id).")
        .def("getArchetypeClassLabel", &CCreature::getArchetypeClassLabel,
             "Return the creature archetype class display label (label, falling back to the archetype class id).");

    py::class_<CPlayer, CCreature, std::shared_ptr<CPlayer>>(m, "CPlayer", "Player-controlled creature.")
        .def("addQuest", &CPlayer::addQuest, "Add a quest to the player quest log.")
        .def("getQuests", &CPlayer::getQuests, "Return the player's active quests.")
        .def("setQuests", &CPlayer::setQuests, "Replace active quests.")
        .def("getCompletedQuests", &CPlayer::getCompletedQuests, "Return the player's completed quests.")
        .def("setCompletedQuests", &CPlayer::setCompletedQuests, "Replace completed quests.")
        .def("getPlayerClassId", &CPlayer::getPlayerClassId, "Return the player's class identity id.")
        .def("setPlayerClassId", &CPlayer::setPlayerClassId, "Set the player's class identity id.")
        .def("getRaceId", &CPlayer::getRaceId, "Return the player's race identity id.")
        .def("setRaceId", &CPlayer::setRaceId, "Set the player's race identity id.")
        .def("checkQuests", &CPlayer::checkQuests, "Move completed quests into the completed quest log.")
        .def("captureQuestJournal", &CPlayer::captureQuestJournal, "Capture the active and completed quest journals.");

    py::class_<CListString, CGameObject, std::shared_ptr<CListString>>(m, "CListString", "String list wrapper object.")
        .def("addValue", &CListString::addValue, "Append a value to the list.")
        .def("getValues", &CListString::getValues, "Return list values.")
        .def("setValues", &CListString::setValues, "Replace list values.");

    py::class_<CListInt, CGameObject, std::shared_ptr<CListInt>>(m, "CListInt", "Integer list wrapper object.")
        .def("addValue", &CListInt::addValue, "Append a value to the list.")
        .def("getValues", &CListInt::getValues, "Return list values.")
        .def("setValues", &CListInt::setValues, "Replace list values.");

    py::class_<CMapStringString, CGameObject, std::shared_ptr<CMapStringString>>(m, "CMapStringString",
                                                                                 "String-to-string map wrapper.")
        .def("getValues", &CMapStringString::getValues, "Return map values.")
        .def("setValues", &CMapStringString::setValues, "Replace map values.");

    py::class_<CMapStringInt, CGameObject, std::shared_ptr<CMapStringInt>>(m, "CMapStringInt",
                                                                           "String-to-int map wrapper.")
        .def("getValues", &CMapStringInt::getValues, "Return map values.")
        .def("setValues", &CMapStringInt::setValues, "Replace map values.");

    py::class_<CMapIntString, CGameObject, std::shared_ptr<CMapIntString>>(m, "CMapIntString",
                                                                           "Int-to-string map wrapper.")
        .def("getValues", &CMapIntString::getValues, "Return map values.")
        .def("setValues", &CMapIntString::setValues, "Replace map values.");

    py::class_<CMapIntInt, CGameObject, std::shared_ptr<CMapIntInt>>(m, "CMapIntInt", "Int-to-int map wrapper.")
        .def("getValues", &CMapIntInt::getValues, "Return map values.")
        .def("setValues", &CMapIntInt::setValues, "Replace map values.");
}
} // namespace nouraajd::bindings
