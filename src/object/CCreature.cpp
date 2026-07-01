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
#include "CCreature.h"
#include <algorithm>
#include <vector>

#include "object/CCreatureClass.h"
#include "object/CCreatureRace.h"

#include "core/CController.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CSlotConfig.h"

#include <utility>

namespace {
template <typename Callback> class ScopeExit {
  public:
    explicit ScopeExit(Callback callback) : callback(std::move(callback)) {}
    ~ScopeExit() {
        if (active) {
            callback();
        }
    }

    void release() { active = false; }

  private:
    Callback callback;
    bool active = true;
};
} // namespace

bool visitablePredicate(std::shared_ptr<CMapObject> object) { return vstd::cast<CVisitable>(object).operator bool(); };

void CCreature::setActions(std::set<std::shared_ptr<CInteraction>> value) {
    actions.clear();
    for (const auto &action : value) {
        addAction(action);
    }
}

std::set<std::shared_ptr<CInteraction>> CCreature::getActions() { return actions; }

int CCreature::getExp() { return exp; }

void CCreature::setExp(int exp) {
    this->exp = exp;
    this->addExp(0);
}

CCreature::CCreature() {}

CCreature::~CCreature() {}

void CCreature::addExpScaled(int scale) {
    int rank = level - scale;
    // TODO: rethink this
    this->addExp(250 * pow(2, -rank));
}

void CCreature::addExp(int exp) {
    if (!isAlive()) {
        return;
    }
    const int before = this->exp;
    this->exp += exp;
    while (this->exp >= getExpForNextLevel()) {
        this->levelUp();
    }
    if (CPlaytestTrace::enabled() && exp != 0) {
        json fields = {
            {"actor", CPlaytestTrace::objectRef(this->ptr<CCreature>())},
            {"after", this->exp},
            {"before", before},
            {"delta", exp},
        };
        CPlaytestTrace::addMapContext(fields, getMap());
        CPlaytestTrace::record("experience_changed", fields);
    }
}

int CCreature::getExpForNextLevel() { return getExpForLevel(level + 1); }

std::shared_ptr<CInteraction> CCreature::getLevelAction() {
    std::string levelString = std::to_string(level);
    if (vstd::ctn(levelling, levelString)) {
        return getGame()->getObjectHandler()->clone<CInteraction>(levelling[levelString]);
    } else {
        return nullptr;
    }
}

std::shared_ptr<CStats> CCreature::getLevelStats() { return levelStats; }

void CCreature::setLevelStats(std::shared_ptr<CStats> _value) { levelStats = _value; }

void CCreature::addItem(std::shared_ptr<CItem> item) {
    std::set<std::shared_ptr<CItem>> list;
    list.insert(item);
    addItems(list);
}

void CCreature::removeItem(std::shared_ptr<CItem> item, bool quest) {
    // TODO: this check should be more polymorphic
    if (!quest && vstd::castable<CPlayer>(this->ptr<CCreature>()) && item->hasTag(CTag::Quest)) {
        vstd::logger::fatal("Tried to drop quest item");
    } else {
        auto itemIt = std::find_if(items.begin(), items.end(), [item](const auto &candidate) {
            return CGameObject::sameInstance(candidate, item);
        });
        if (itemIt != items.end()) {
            items.erase(itemIt);
            if (CPlaytestTrace::enabled()) {
                json fields = {
                    {"item", CPlaytestTrace::objectRef(item)},
                    {"owner", CPlaytestTrace::objectRef(this->ptr<CCreature>())},
                    {"questRemoval", quest},
                };
                CPlaytestTrace::addMapContext(fields, getMap());
                CPlaytestTrace::record("inventory_removed", fields);
            }
            recordDirectPropertyChanged("items");
            signal("inventoryChanged");
        }
    }
}

void CCreature::removeItem(std::function<bool(std::shared_ptr<CItem>)> item_pred, bool quest) {
    for (auto item : items) {
        if (item_pred(item)) {
            removeItem(item, quest);
            break;
        }
    }
}

std::set<std::shared_ptr<CItem>> CCreature::getInInventory() { return items; }

std::set<std::shared_ptr<CInteraction>> CCreature::getInteractions() { return getEffectiveInteractions(); }

std::set<std::shared_ptr<CInteraction>> CCreature::getEffectiveInteractions() {
    // Composes the creature's effective interaction set from every source that
    // backs it today, de-duplicated so identical actions are never exposed
    // twice. Dedupe key is the action typeId, falling back to its name when the
    // typeId is empty (matching the identity rules CGameObject uses elsewhere).
    //
    // Precedence (lowest first, so later sources override earlier duplicates):
    //   1. race actions          -- extension point (no backing object yet)
    //   2. creature-class actions -- extension point (no backing object yet)
    //   3. class level unlocks    -- levelling entries unlocked up to the
    //                                current level (the model expresses class
    //                                level unlocks through `levelling` today)
    //   4. concrete own actions   -- the creature's own configured actions win
    //
    // Race / creature-class archetype objects (CCreatureClass) do not exist in
    // the codebase yet, so there is nothing to pull their actions from. The
    // ordered composition below is structured so those sources slot in ahead of
    // the level unlocks once the archetype foundation lands, without changing
    // the concrete-actions-win precedence.

    std::vector<std::shared_ptr<CInteraction>> ordered;

    auto dedupeKey = [](const std::shared_ptr<CInteraction> &action) -> std::string {
        std::string typeId = action->getTypeId();
        if (!typeId.empty()) {
            return "T:" + typeId;
        }
        return "N:" + action->getName();
    };

    // 1-2. race / creature-class actions: extension point. Nothing to add until
    //      the archetype foundation provides those objects.

    // 3. class level unlocks: levelling entries unlocked up to the current
    //    level. Keys are the level at which the entry unlocks (see
    //    getLevelAction / levelUp).
    for (const auto &[levelKey, action] : levelling) {
        if (!action) {
            continue;
        }
        int unlockLevel = 0;
        try {
            unlockLevel = std::stoi(levelKey);
        } catch (...) {
            // Non-numeric levelling keys are not level-gated unlocks; include
            // them so no configured action is silently dropped.
            unlockLevel = 0;
        }
        if (unlockLevel <= level) {
            ordered.push_back(action);
        }
    }

    // 4. concrete own actions: added last so they win duplicate-key conflicts.
    for (const auto &action : actions) {
        if (action) {
            ordered.push_back(action);
        }
    }

    // De-duplicate by key, keeping the last occurrence so higher-precedence
    // sources (added later above) override lower-precedence duplicates.
    std::map<std::string, std::shared_ptr<CInteraction>> byKey;
    for (const auto &action : ordered) {
        byKey[dedupeKey(action)] = action;
    }

    std::set<std::shared_ptr<CInteraction>> effective;
    for (const auto &[key, action] : byKey) {
        effective.insert(action);
    }
    return effective;
}

CItemMap CCreature::getEquipped() { return equipped; }

void CCreature::setEquipped(CItemMap value) {
    equipped = value; // TODO: rethink equipped changed here
    recordDirectPropertyChanged("equipped");
}

void CCreature::addItems(std::set<std::shared_ptr<CItem>> items) {
    for (std::shared_ptr<CItem> it : items) {
        if (!it) {
            vstd::logger::warning("Skipping null item while adding inventory to", to_string());
            continue;
        }
        this->items.insert(it);
        if (CPlaytestTrace::enabled()) {
            json fields = {
                {"item", CPlaytestTrace::objectRef(it)},
                {"owner", CPlaytestTrace::objectRef(this->ptr<CCreature>())},
            };
            CPlaytestTrace::addMapContext(fields, getMap());
            CPlaytestTrace::record("inventory_added", fields);
        }
        recordDirectPropertyChanged("items");
        signal("inventoryChanged");
    }
}

void CCreature::addItem(std::string item) { addItem(getGame()->createObject<CItem>(item)); }

void CCreature::heal(int i) {
    vstd::fail_if(i < 0, "Tried to heal negative value!");
    auto hpMax = getHpMax();
    const int before = hp;
    if (hp > hpMax) {
        return;
    }
    if (i == 0) {
        hp = hpMax;
    } else {
        hp += i;
    }
    if (hp > hpMax) {
        hp = hpMax;
    }
    if (hp != before) {
        recordDirectPropertyChanged("hp");
    }
}

void CCreature::healProc(float i) {
    int tmp = hp;
    heal(i / 100.0 * getHpMax());
    vstd::logger::debug(to_string(), "restored", hp - tmp, "hp");
}

void CCreature::hurt(int i) {
    std::shared_ptr<CDamage> damage = std::make_shared<CDamage>();
    damage->setNormal(i);
    hurt(damage);
}

void CCreature::hurt(float i) { hurt(int(round(i))); }

int CCreature::getExpRatio() {
    return (float)((exp - getExpForLevel(level))) / (float)(getExpForLevel(level + 1) - getExpForLevel(level)) * 100.0;
}

// TODO: resistance and blocking to be more generic
void CCreature::takeDamage(int rawDamage) {
    auto stats = getStats();
    if (rawDamage < 0) {
        rawDamage = 0;
    }
    int damageAfterArmor = rawDamage * ((100 - stats->getArmor()) / 100.0);
    if (damageAfterArmor < 0) {
        damageAfterArmor = 0;
    }
    int blockDice = rand() % 100;
    if (blockDice >= stats->getBlock()) {
        vstd::logger::debug(to_string(), "armor saved from", rawDamage - damageAfterArmor, "damage");
        const int before = hp;
        hp -= damageAfterArmor;
        if (hp != before) {
            recordDirectPropertyChanged("hp");
        }
    } else {
        vstd::logger::debug(getName(), "blocked", rawDamage, "damage");
    }
}

CInteractionMap CCreature::getLevelling() { return levelling; }

void CCreature::setLevelling(CInteractionMap value) { levelling = value; }

void CCreature::setItems(std::set<std::shared_ptr<CItem>> value) {
    CGameObject::PropertyNotificationBatch notificationBatch(*this);
    items.clear(); // TODO: rethink inventory changed here
    recordDirectPropertyChanged("items");
    addItems(value);
}

std::set<std::shared_ptr<CItem>> CCreature::getItems() { return items; }

void CCreature::hurt(std::shared_ptr<CDamage> damage) {
    auto stats = getStats();
    takeDamage(damage->getNormal() * (100 - stats->getNormalResist()) / 100.0);
    takeDamage(damage->getThunder() * (100 - stats->getThunderResist()) / 100.0);
    takeDamage(damage->getFrost() * (100 - stats->getFrostResist()) / 100.0);
    takeDamage(damage->getFire() * (100 - stats->getFireResist()) / 100.0);
    takeDamage(damage->getShadow() * (100 - stats->getShadowResist()) / 100.0);

    vstd::logger::debug(getType(), "took damage:", JSONIFY(damage));
}

int CCreature::getDmg() {
    auto stats = getStats();
    int critDice = rand() % 100;
    int attDice = rand() % 100;
    int dmgMin = std::min(stats->getDmgMin(), stats->getDmgMax());
    int dmgMax = std::max(stats->getDmgMin(), stats->getDmgMax());
    int dmg = rand() % (dmgMax + 1 - dmgMin) + dmgMin;
    dmg += stats->getDamage();
    attDice -= stats->getAttack();
    if (attDice < stats->getHit()) {
        if (critDice < stats->getCrit()) {
            dmg *= 2;
            vstd::logger::debug("Critical!");
        }
        return dmg;
    } else {
        vstd::logger::debug("Missed!");
        return 0;
    }
}

int CCreature::getScale() { return level + sw; }

bool CCreature::isAlive() { return hp > 0; }

void CCreature::addAction(std::shared_ptr<CInteraction> action) {
    if (!action) {
        return;
    }
    // Action merge contract (docs/design/creature_archetypes.md, "Creature action
    // merge contract"): actions are composed in precedence order and deduplicated by
    // configured identity. The identity key is the action `typeId`, falling back to
    // `name` only when `typeId` is empty. A later (more specific) source overrides an
    // earlier one, so duplicate actions (e.g. a second `Attack`) collapse to a single
    // entry and do not accumulate, while unique concrete overrides are preserved.
    auto sameAction = [&action](const std::shared_ptr<CInteraction> &candidate) {
        if (!candidate) {
            return false;
        }
        const std::string &candidateTypeId = candidate->getTypeId();
        const std::string &actionTypeId = action->getTypeId();
        if (!candidateTypeId.empty() || !actionTypeId.empty()) {
            return candidateTypeId == actionTypeId;
        }
        return candidate->getName() == action->getName();
    };
    auto existing = std::find_if(actions.begin(), actions.end(), sameAction);
    if (existing != actions.end()) {
        if (CGameObject::sameInstance(*existing, action)) {
            return;
        }
        actions.erase(existing);
    }
    actions.insert(action);
    signal("interactionsChanged");
}

void CCreature::addEffect(std::shared_ptr<CEffect> effect) {
    if (!effect) {
        vstd::logger::warning("Skipping null effect for", to_string());
        return;
    }
    if (vstd::ctn(effects, effect, CGameObject::sameConfiguredType)) {
        vstd::logger::debug(effect->to_string(), "skipping already present effect for", this->to_string());
    } else {
        vstd::logger::debug(effect->to_string(), "starts for", this->to_string());
        effects.insert(effect);
        recordDirectPropertyChanged("effects");
        signal("effectsChanged");
    }
}

int CCreature::getMana() { return mana; }

void CCreature::setMana(int mana) {
    this->mana = mana;
    recordDirectPropertyChanged("mana");
}

void CCreature::addMana(int i) {
    vstd::fail_if(i < 0, "Tried to add negative mana!");
    auto manaMax = getManaMax();
    const int before = mana;
    if (mana > manaMax) {
        return;
    }
    if (i == 0) {
        mana = manaMax;
    } else {
        mana += i;
    }
    if (mana > manaMax) {
        mana = manaMax;
    }
    if (mana != before) {
        recordDirectPropertyChanged("mana");
    }
}

void CCreature::addManaProc(float i) {
    int tmp = mana;
    addMana(i / 100.0 * getManaMax());
    vstd::logger::debug(to_string(), "restored", mana - tmp, "mana");
}

void CCreature::takeMana(int i) {
    vstd::fail_if(i < 0, "Tried to take negative mana value!");
    const int before = mana;
    mana = std::max(0, mana - i);
    if (mana != before) {
        recordDirectPropertyChanged("mana");
    }
}

bool CCreature::isPlayer() {
    auto map = getMap();
    if (!map) {
        return false;
    }
    const std::shared_ptr<CPlayer> player = map->getPlayer();
    return player && CGameObject::sameInstance(player, this->ptr<CPlayer>());
}

int CCreature::getHpRatio() {
    auto hpMax = getHpMax();
    if (hp > hpMax) {
        return 100;
    }
    if (hpMax <= 0) {
        return hp > 0 ? 100 : 0;
    }
    if (hp < 0) {
        return 0;
    }
    return (float)hp / (float)hpMax * 100.0;
}

int CCreature::getManaRatio() {
    auto manaMax = getManaMax();
    if (mana > manaMax) {
        return 100;
    }
    if (manaMax == 0) {
        return 100;
    }
    if (mana < 0) {
        return 0;
    }
    return (float)mana / (float)manaMax * 100.0;
}

int CCreature::getHp() { return hp; }

int CCreature::getManaMax() { return getStats()->getMainValue() * 7; }

int CCreature::getLevel() { return level; }

void CCreature::setWeapon(std::shared_ptr<CWeapon> weapon) { this->equipItem(std::to_string(0), weapon); }

void CCreature::setArmor(std::shared_ptr<CArmor> armor) { this->equipItem(std::to_string(3), armor); }

// TODO: make method unequip instead of equip null
void CCreature::equipItem(std::string i, std::shared_ptr<CItem> newItem) {
    vstd::fail_if(newItem && !getMap()->getGame()->getSlotConfiguration()->canFit(i, newItem),
                  "Tried to insert" + (newItem ? newItem->getType() : "null") + "into slot" + i);

    // Cursed items cannot leave the slot they occupy: unequipping or swapping out a
    // cursed item is refused until the curse is lifted (removeTag(CTag::Cursed)).
    // Re-equipping the same instance is a no-op and stays allowed.
    if (vstd::ctn(equipped, i) && equipped.at(i)->hasTag(CTag::Cursed) &&
        !CGameObject::sameInstance(newItem, equipped.at(i))) {
        return;
    }

    if (vstd::ctn(equipped, i)) {
        std::shared_ptr<CItem> oldItem = equipped.at(i);

        getMap()->getEventHandler()->gameEvent(
            oldItem, std::make_shared<CGameEventCaused>(CGameEvent::CType::onUnequip, this->ptr<CCreature>()));
        this->addItem(oldItem);
        if (CGameObject::sameInstance(newItem, oldItem)) {
            newItem = nullptr;
        }
    }
    if (newItem) {
        getMap()->getEventHandler()->gameEvent(
            newItem, std::make_shared<CGameEventCaused>(CGameEvent::CType::onEquip, this->ptr<CCreature>()));
        removeItem(newItem);
        equipped[i] = newItem;
        recordDirectPropertyChanged("equipped");
        signal("equippedChanged");
    } else {
        if (equipped.erase(i)) {
            recordDirectPropertyChanged("equipped");
            signal("equippedChanged");
        }
    }

    const int previousHp = hp;
    const int previousMana = mana;
    hp = std::min(hp, getHpMax());
    mana = std::min(mana, getManaMax());
    if (hp != previousHp) {
        recordDirectPropertyChanged("hp");
    }
    if (mana != previousMana) {
        recordDirectPropertyChanged("mana");
    }
}

bool CCreature::hasInInventory(std::shared_ptr<CItem> item) {
    return std::any_of(items.begin(), items.end(),
                       [item](const auto &candidate) { return CGameObject::sameInstance(candidate, item); });
}

bool CCreature::hasInInventory(std::function<bool(std::shared_ptr<CItem>)> item) {
    return std::any_of(items.begin(), items.end(), item);
}

bool CCreature::hasItem(std::shared_ptr<CItem> item) { return hasInInventory(item) || hasEquipped(item); }

bool CCreature::hasItem(std::function<bool(std::shared_ptr<CItem>)> item) {
    return hasInInventory(item) || hasEquipped(item);
}

int CCreature::countItems(std::string typeId) {
    return std::count_if(items.begin(), items.end(),
                         [&typeId](const std::shared_ptr<CItem> &item) { return item && item->getTypeId() == typeId; });
}

std::shared_ptr<CWeapon> CCreature::getWeapon() { return vstd::cast<CWeapon>(getItemAtSlot("0")); }

std::shared_ptr<CArmor> CCreature::getArmor() { return vstd::cast<CArmor>(getItemAtSlot("3")); }

// TODO: get rid of this, calculate level automatically
void CCreature::levelUp() {
    level++;
    if (usesArchetypeComposition()) {
        // Composed level-up path (creature carries a race and/or creatureClass).
        // Class-derived level unlocks are NOT mutated/serialized into the creature's
        // own `actions` set: getEffectiveInteractions already surfaces every
        // `levelling` entry whose unlock level is at or below the current level
        // (src/object/CCreature.cpp getEffectiveInteractions, the unlockLevel <= level
        // gate). Raising `level` therefore changes the derived interaction set on its
        // own, so we only signal `interactionsChanged` for observers to re-query the
        // composed set -- no duplicate serialized actions accumulate across level-ups.
        signal("interactionsChanged");
        heal(0);
        addMana(0);
    } else {
        // Legacy fallback compatibility contract (docs/design/creature_archetypes.md,
        // "Legacy fallback compatibility contract"): a creature with no race and no
        // creatureClass uses this legacy level-up path exactly -- increment level and
        // apply the concrete template's own `levelling` unlock (getLevelAction) by
        // folding it into `actions`. This preserves the historical behavior where the
        // unlock is serialized into the creature's own action set.
        // TODO: dynamic action calculation
        addAction(getLevelAction());
        heal(0);
        addMana(0);
    }
    if (level > 1) {
        vstd::logger::debug(to_string(), "is now level:", level);
    }
}

std::set<std::shared_ptr<CItem>> CCreature::getAllItems() {
    std::set<std::shared_ptr<CItem>> allItems;
    allItems.insert(items.begin(), items.end());
    for (auto it : equipped) {
        if (it.second) {
            allItems.insert(it.second);
        }
    }
    return allItems;
}

bool CCreature::hasEquipped(std::function<bool(std::shared_ptr<CItem>)> item) {
    for (auto it : equipped) {
        if (item(it.second)) {
            return true;
        }
    }
    return false;
}

bool CCreature::hasEquipped(std::shared_ptr<CItem> item) {
    for (auto it : equipped) {
        if (CGameObject::sameInstance(it.second, item)) {
            return true;
        }
    }
    return false;
}

int CCreature::getSw() const { return sw; }

void CCreature::setSw(int _value) { sw = _value; }

std::shared_ptr<CStats> CCreature::getBaseStats() { return baseStats; }

void CCreature::setBaseStats(std::shared_ptr<CStats> _value) { baseStats = _value; }

int CCreature::getHpMax() {
    return getStats()->getStamina() * 7;
    ;
}

std::shared_ptr<CItem> CCreature::getItemAtSlot(std::string slot) {
    if (vstd::ctn(equipped, slot)) {
        return equipped.at(slot);
    }
    return nullptr;
}

std::string CCreature::getSlotWithItem(std::shared_ptr<CItem> item) {
    for (auto it = equipped.begin(); it != equipped.end(); it++) {
        if (CGameObject::sameInstance((*it).second, item)) {
            return (*it).first;
        }
    }
    return "-1";
}

void CCreature::setHp(int value) {
    hp = value;
    recordDirectPropertyChanged("hp");
}

int CCreature::getManaRegRate() { return getStats()->getMainValue() / 10 + 1; }

int CCreature::getGold() { return gold; }

void CCreature::setGold(int value) {
    const int before = gold;
    gold = value;
    if (CPlaytestTrace::enabled() && before != value) {
        json fields = {
            {"actor", CPlaytestTrace::objectRef(this->ptr<CCreature>())},
            {"after", value},
            {"before", before},
            {"delta", value - before},
        };
        CPlaytestTrace::addMapContext(fields, getMap());
        CPlaytestTrace::record("gold_changed", fields);
    }
    recordDirectPropertyChanged("gold");
}

void CCreature::beforeMove() {
    auto map = getMap();
    pendingMoveOrigin = map ? map->normalizeCoords(getCoords()) : getCoords();
    ScopeExit clearOnFailure([this]() { pendingMoveOrigin.reset(); });
    auto self = this->ptr<CCreature>();

    auto func = [self](std::shared_ptr<CMapObject> object) {
        self->getMap()->getEventHandler()->gameEvent(
            object, std::make_shared<CGameEventCaused>(CGameEvent::CType::onLeave, self));
    };

    getMap()->forObjectsAtCoords(getCoords(), func, visitablePredicate);
    clearOnFailure.release();
}

void CCreature::afterMove() {
    ScopeExit clearPendingMoveOrigin([this]() { pendingMoveOrigin.reset(); });
    auto self = this->ptr<CCreature>();
    auto map = getMap();
    if (!map) {
        return;
    }
    const auto arrival = map->normalizeCoords(getCoords());

    auto moverStillAtArrival = [self, map, arrival]() {
        return self->isAlive() && self->getMap() == map &&
               CGameObject::sameRuntimeIdentity(map->getObjectByName(self->getName()), self) &&
               map->normalizeCoords(self->getCoords()) == arrival;
    };

    auto fightPred = [self, map](std::shared_ptr<CMapObject> object) {
        auto other = vstd::cast<CCreature>(object);
        return other && !CGameObject::sameInstance(self, object) && !self->isNpc() && !other->isNpc() &&
               !self->isAffiliatedWith(object) && self->getMap() == map &&
               CGameObject::sameRuntimeIdentity(map->getObjectByName(self->getName()), self) &&
               other->getMap() == map &&
               CGameObject::sameRuntimeIdentity(map->getObjectByName(other->getName()), other);
    };

    std::vector<std::shared_ptr<CCreature>> opponents;
    auto fightAction = [&opponents](auto object) {
        if (auto creature = vstd::cast<CCreature>(object)) {
            opponents.push_back(creature);
        }
    };

    auto eventAction = [self, map](auto object) {
        map->getEventHandler()->gameEvent(object, std::make_shared<CGameEventCaused>(CGameEvent::CType::onEnter, self));
    };

    map->forObjectsAtCoords(arrival, fightAction, fightPred);
    if (!opponents.empty()) {
        const auto result = CFightHandler::fightManyResult(self, opponents);
        // Post-combat position policy. The fight ran because the mover stepped into a
        // hostile cell. If the attacker was defeated or otherwise removed it already left
        // the arrival square, so there is nothing more to do. For the player every
        // resolved encounter (victory, cancellation or stall) restores the pre-step origin
        // via the non-hook relocation helper, so the player never lingers inside the
        // hostile cell and onStep/onEnter never fire there. Non-player movers keep the
        // legacy behaviour: only a victory lets them stay and continue onto onStep/onEnter.
        if (!moverStillAtArrival()) {
            return;
        }
        if (self->isPlayer()) {
            if (pendingMoveOrigin.has_value()) {
                self->relocateWithoutMoveHooks(*pendingMoveOrigin);
            }
            return;
        }
        if (result.outcome != CFightOutcome::AttackerVictory) {
            return;
        }
    }

    if (!moverStillAtArrival()) {
        return;
    }
    if (map->getTile(arrival)) {
        map->getTile(arrival)->onStep(self);
    }
    if (!moverStillAtArrival()) {
        return;
    }
    map->forObjectsAtCoords(arrival, eventAction, visitablePredicate);
}

const std::optional<Coords> &CCreature::getPendingMoveOrigin() const { return pendingMoveOrigin; }

void CCreature::addGold(int gold) { this->setGold(this->getGold() + gold); }

void CCreature::takeGold(int gold) { this->setGold(this->getGold() - gold); }

std::set<std::shared_ptr<CEffect>> CCreature::getEffects() const { return effects; }

void CCreature::onEnter(std::shared_ptr<CGameEvent>) {}

void CCreature::onLeave(std::shared_ptr<CGameEvent>) {}

void CCreature::onDestroy(std::shared_ptr<CGameEvent>) {
    if (!effects.empty()) {
        effects.clear();
        recordDirectPropertyChanged("effects");
    }
}

void CCreature::setEffects(const std::set<std::shared_ptr<CEffect>> &value) {
    CGameObject::PropertyNotificationBatch notificationBatch(*this);
    effects.clear();
    recordDirectPropertyChanged("effects");
    for (const auto &effect : value) {
        addEffect(effect);
    }
}

std::shared_ptr<CController> CCreature::getController() {
    return controller ? controller : std::make_shared<CController>();
}

void CCreature::setController(std::shared_ptr<CController> controller) { this->controller = controller; }

std::string CCreature::to_string() {
    return vstd::join({CGameObject::to_string(), "(",
                       vstd::join({vstd::str(getPosX()), vstd::str(getPosY()), vstd::str(getPosZ())}, ","), ")"},
                      "");
}

std::shared_ptr<CFightController> CCreature::getFightController() { return fightController; }

void CCreature::setFightController(std::shared_ptr<CFightController> fightController) {
    CCreature::fightController = fightController;
}

bool CCreature::isNpc() { return npc; }

void CCreature::setNpc(bool value) { npc = value; }

// TODO: make this a CGameEvent
void CCreature::useAction(std::shared_ptr<CInteraction> action, std::shared_ptr<CCreature> creature) {
    vstd::fail_if(!std::any_of(actions.begin(), actions.end(), [action](const auto &candidate) {
        return CGameObject::sameInstance(candidate, action);
    }));
    action->onAction(this->ptr<CCreature>(), creature);
    if (creature->getArmor()) {
        if (creature->getArmor()->getInteraction()) {
            creature->getArmor()->getInteraction()->onAction(creature, this->ptr<CCreature>());
        }
    }
}

void CCreature::removeEffect(std::shared_ptr<CEffect> effect) {
    auto effectIt = std::find_if(effects.begin(), effects.end(), [effect](const auto &candidate) {
        return CGameObject::sameInstance(candidate, effect);
    });
    if (effectIt != effects.end()) {
        effects.erase(effectIt);
        recordDirectPropertyChanged("effects");
    }
    signal("effectsChanged");
}

void CCreature::useItem(std::shared_ptr<CItem> item) {
    vstd::fail_if(!hasInInventory(item), "Tried to use item not in inventory!");
    const bool restores_hp = item->hasTag(CTag::Heal);
    const bool restores_mana = item->hasTag(CTag::Mana);
    const bool can_restore_hp = restores_hp && getHp() < getHpMax();
    const bool can_restore_mana = restores_mana && getMana() < getManaMax();
    if ((restores_hp || restores_mana) && !can_restore_hp && !can_restore_mana) {
        return;
    }
    getMap()->getEventHandler()->gameEvent(item,
                                           std::make_shared<CGameEventCaused>(CGameEvent::CType::onUse, this->ptr()));
    if (item->isDisposable()) {
        removeItem(item);
    }
}

void CCreature::setLevel(int level) { this->level = level; }

int CCreature::getExpForLevel(int level) { return (level - 1) * level * 500; }

void CCreature::removeQuestItem(std::shared_ptr<CItem> item) { removeItem(item, true); }

void CCreature::removeQuestItem(std::function<bool(std::shared_ptr<CItem>)> item) { removeItem(item, true); }

std::shared_ptr<CStats> CCreature::getStats() {
    // Branch on archetype presence so legacy creatures (race == null and
    // creatureClass == null, i.e. every creature pre-migration) keep the exact
    // legacy stat block, while archetype creatures get the composed aggregate.
    return usesArchetypeComposition() ? buildComposedStats() : buildLegacyStats();
}

std::shared_ptr<CStats> CCreature::buildComposedStats() {
    // Composed stat precedence (docs/design/creature_archetypes.md, "Creature stat
    // precedence contract"), applied least- to most-specific into a fresh aggregate
    // so no source CStats object is ever mutated:
    //   1. race.baseStats
    //   2. creatureClass.baseStats
    //   3. creature.baseStats
    //   4. creatureClass.levelStats per level
    //   5. creature.levelStats per level
    //   6. equipment bonuses
    //   7. effect bonuses
    // The equipment-then-effects tail keeps the same relative order as the legacy
    // path. Each archetype reference is independently null-guarded: usesArchetype-
    // Composition() only guarantees at least one of race / creatureClass is set.
    std::shared_ptr<CStats> ret = std::make_shared<CStats>();
    // Main stat is a *selected* (not accumulated) field, so it must be set explicitly
    // (CStats::addBonus copies only numeric properties). The creatureClass is
    // authoritative for it (E02/S04/SS03): a class that names a main stat wins over the
    // legacy/race creature.baseStats main stat; with no class, or a class that leaves it
    // empty, this falls back to the legacy creature.baseStats main stat. The composed
    // path must apply this here because archetype creatures never run buildLegacyStats().
    if (creatureClass && !creatureClass->getMainStat().empty()) {
        ret->setMainStat(creatureClass->getMainStat());
    } else {
        ret->setMainStat(getBaseStats()->getMainStat());
    }
    // 1. race.baseStats.
    if (race && race->getBaseStats()) {
        ret->addBonus(race->getBaseStats());
    }
    // 2. creatureClass.baseStats.
    if (creatureClass && creatureClass->getBaseStats()) {
        ret->addBonus(creatureClass->getBaseStats());
    }
    // 3. creature.baseStats (concrete template's own base).
    ret->addBonus(getBaseStats());
    // 4. creatureClass.levelStats per level.
    if (creatureClass && creatureClass->getLevelStats()) {
        for (int i = 0; i < level; i++) {
            ret->addBonus(creatureClass->getLevelStats());
        }
    }
    // 5. creature.levelStats per level.
    for (int i = 0; i < level; i++) {
        ret->addBonus(getLevelStats());
    }
    // 6. equipment bonuses.
    for (auto [slot, item] : getEquipped()) {
        if (item) {
            ret->addBonus(item->getBonus());
        }
    }
    // 7. effect bonuses.
    for (auto effect : getEffects()) {
        if (effect) {
            ret->addBonus(effect->getBonus());
        }
    }
    return ret;
}

std::shared_ptr<CStats> CCreature::buildLegacyStats() {
    // Stat precedence contract (docs/design/creature_archetypes.md, "Creature stat
    // precedence contract"): effective stats are composed least- to most-specific:
    //   1. race.baseStats             -- extension point (no backing object yet)
    //   2. creatureClass.baseStats    -- extension point (no backing object yet)
    //   3. creature.baseStats         -- concrete template's own base (legacy)
    //   4. creatureClass.levelStats   -- extension point, per level (no object yet)
    //   5. creature.levelStats        -- concrete template's per-level growth (legacy)
    //   6. equipment bonuses
    //   7. effect bonuses
    // Main stat is selected from creatureClass.baseStats first, falling back to the
    // legacy creature.baseStats mainStat. The race / creature-class archetype objects
    // (CCreatureClass) do not exist yet, so positions 1, 2, 4 and the class-first main
    // stat are extension points that contribute nothing today; they slot in here
    // without disturbing the equipment-then-effects tail or the legacy fallback.
    // Legacy fallback compatibility contract (same doc, "Legacy fallback
    // compatibility contract"): for a creature with no race and no creatureClass
    // (every creature today) this composes the legacy stat block exactly.
    std::shared_ptr<CStats> ret = std::make_shared<CStats>();
    // Main stat selection (class-first, authoritative): the composed block's mainStat is a
    // *selected* (not accumulated) field -- CStats::addBonus copies only numeric properties, so
    // the std::string mainStat must be assigned explicitly. When the creature has a composed
    // creatureClass that declares a main stat, that class main stat is AUTHORITATIVE and wins
    // over the legacy/race creature.baseStats main stat. A legacy creature with no class -- or a
    // class with an empty main stat -- falls back to the legacy creature.baseStats.mainStat
    // exactly, preserving the no-archetype path (EPIC_02/STORY_04/SUBSTORY_03).
    std::string composedMainStat = getBaseStats()->getMainStat();
    if (creatureClass && !creatureClass->getMainStat().empty()) {
        composedMainStat = creatureClass->getMainStat();
    }
    ret->setMainStat(composedMainStat);
    // 1-2. race / creature-class baseStats: extension point (nothing to add yet).
    // 3. creature.baseStats (legacy concrete base).
    ret->addBonus(getBaseStats());
    // 4. creatureClass.levelStats per level: extension point (nothing to add yet).
    // 5. creature.levelStats per level (legacy concrete growth).
    for (int i = 0; i < level; i++) {
        ret->addBonus(getLevelStats());
    }
    // 6. equipment bonuses.
    for (auto [slot, item] : getEquipped()) {
        if (item) {
            ret->addBonus(item->getBonus());
        }
    }
    // 7. effect bonuses.
    for (auto effect : getEffects()) {
        if (effect) {
            ret->addBonus(effect->getBonus());
        }
    }
    return ret;
}

std::string CCreature::getArchetypeRaceId() {
    std::string typeId = getTypeId();
    if (!typeId.empty()) {
        return typeId;
    }
    return getName();
}

std::string CCreature::getArchetypeClassId() {
    std::string typeId = getTypeId();
    if (!typeId.empty()) {
        return typeId;
    }
    return getName();
}

std::string CCreature::getArchetypeRaceLabel() {
    std::string label = getLabel();
    if (!label.empty()) {
        return label;
    }
    return getArchetypeRaceId();
}

std::string CCreature::getArchetypeClassLabel() {
    std::string label = getLabel();
    if (!label.empty()) {
        return label;
    }
    return getArchetypeClassId();
}

std::shared_ptr<CCreatureRace> CCreature::getRace() { return race; }

// A null race is valid: it marks a legacy (non-archetype) creature.
void CCreature::setRace(std::shared_ptr<CCreatureRace> value) { race = value; }

std::shared_ptr<CCreatureClass> CCreature::getCreatureClass() { return creatureClass; }

// A null creatureClass is valid: it marks a legacy (non-archetype) creature.
void CCreature::setCreatureClass(std::shared_ptr<CCreatureClass> value) { creatureClass = value; }

bool CCreature::usesArchetypeComposition() { return race != nullptr || creatureClass != nullptr; }
