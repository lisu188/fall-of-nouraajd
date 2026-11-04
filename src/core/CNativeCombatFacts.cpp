/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2026  Andrzej Lis

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
#include "CNativeCombatFacts.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CStats.h"
#include "handler/CEventHandler.h"
#include "object/CCreature.h"

struct CNativeCombatFact {
    const std::string kind;
    const std::shared_ptr<CCreature> cause;
    const std::shared_ptr<CCreature> victim;
    const std::shared_ptr<CGameObject> producer;
    const bool connected = false;
    const int damage = 0;
    const DamageValue channels;
    const int hpBefore = 0;
    const int hpAfter = 0;
    const int manaAtCommit = 0;
};

struct CNativeCombatBatch {
    static constexpr std::size_t MAX_FACTS = 128;
    static constexpr std::size_t MAX_DEPTH = 32;
    std::weak_ptr<CGameContext> context;
    std::weak_ptr<CGame> game;
    std::shared_ptr<CMap> map;
    std::uint64_t generation = 0;
    std::size_t depth = 0;
    bool aborted = false;
    bool overflow = false;
    bool publishing = false;
    std::vector<std::shared_ptr<const CNativeCombatFact>> facts;

    bool current() const {
        auto owner = context.lock();
        auto active = game.lock();
        return !aborted && !overflow && owner && owner->isActive() &&
               owner->isTransitionGenerationCurrent(generation) && active && active->getContext() == owner &&
               active->getMap() == map && map->getBoolProperty("nativeCombatFacts");
    }

    bool owns(const std::shared_ptr<CCreature> &cause, const std::shared_ptr<CCreature> &victim) const {
        auto active = game.lock();
        return current() && cause && victim && cause->getGame() == active && victim->getGame() == active &&
               cause->getMap() == map && victim->getMap() == map && map->getObjectByName(cause->getName()) == cause &&
               map->getObjectByName(victim->getName()) == victim;
    }
};

namespace {
std::shared_ptr<CGameEvent> makeEvent(const std::shared_ptr<const CNativeCombatFact> &captured,
                                      const std::shared_ptr<CGame> &game) {
    auto event = std::make_shared<CGameEventCaused>(captured->kind, captured->cause);
    event->setGame(game);
    event->setStringProperty("combatKind", captured->kind);
    event->setObjectProperty("combatProducer", captured->producer);
    if (captured->kind == CGameEvent::CType::onCombatAttempt) {
        event->setNumericProperty("combatManaAtCommit", captured->manaAtCommit);
    } else if (captured->kind == CGameEvent::CType::onCombatRoll) {
        event->setBoolProperty("combatConnected", captured->connected);
        event->setNumericProperty("combatDamage", captured->damage);
    } else {
        event->setNumericProperty("combatNormal", captured->channels.normal);
        event->setNumericProperty("combatThunder", captured->channels.thunder);
        event->setNumericProperty("combatFrost", captured->channels.frost);
        event->setNumericProperty("combatFire", captured->channels.fire);
        event->setNumericProperty("combatShadow", captured->channels.shadow);
        event->setNumericProperty("combatHpBefore", captured->hpBefore);
        event->setNumericProperty("combatHpAfter", captured->hpAfter);
    }
    return event;
}
} // namespace

CNativeCombatScope::CNativeCombatScope(const std::shared_ptr<CGame> &game) {
    auto map = game ? game->getMap() : nullptr;
    if (!map || !map->getBoolProperty("nativeCombatFacts")) {
        return;
    }
    context = game->getContext();
    if (!context || !context->isActive()) {
        return;
    }
    batch = context->nativeCombatBatch;
    if (!batch) {
        batch = std::make_shared<CNativeCombatBatch>();
        batch->context = context;
        batch->game = game;
        batch->map = std::move(map);
        batch->generation = context->captureTransitionGeneration();
        context->nativeCombatBatch = batch;
    }
    if (!batch->current()) {
        batch.reset();
        return;
    }
    if (batch->depth >= CNativeCombatBatch::MAX_DEPTH) {
        batch->overflow = true;
        batch.reset();
        return;
    }
    ++batch->depth;
    joined = true;
}

CNativeCombatScope::~CNativeCombatScope() noexcept {
    if (joined) {
        // An exception or missing completion cannot publish a partly committed operation.
        batch->aborted = true;
        --batch->depth;
        if (batch->depth == 0 && !batch->publishing && context->nativeCombatBatch == batch) {
            context->nativeCombatBatch.reset();
        }
    }
}

void CNativeCombatScope::finish() {
    if (!joined) {
        return;
    }
    joined = false;
    --batch->depth;
    if (batch->depth != 0 || batch->publishing) {
        return;
    }
    const auto release = [&] {
        batch->publishing = false;
        if (context->nativeCombatBatch == batch) {
            context->nativeCombatBatch.reset();
        }
    };
    batch->publishing = true;
    try {
        for (std::size_t index = 0; index < batch->facts.size() && batch->current(); ++index) {
            const auto fact = batch->facts[index];
            const auto current = [batch = batch, fact] { return batch->owns(fact->cause, fact->victim); };
            if (!current() || !batch->map->getEventHandler()->combatEvent(
                                  fact->victim, fact->kind,
                                  [fact, game = batch->game.lock()] { return makeEvent(fact, game); }, current)) {
                break;
            }
        }
    } catch (...) {
        release();
        throw;
    }
    release();
    if (batch->overflow) {
        throw std::runtime_error("Native combat fact batch exceeded its fixed work budget.");
    }
}

CNativeCombatFacts::CNativeCombatFacts(std::shared_ptr<CCreature> cause, std::shared_ptr<CCreature> victim)
    : cause(std::move(cause)), victim(std::move(victim)) {
    auto game = this->victim ? this->victim->getGame() : nullptr;
    auto map = game ? game->getMap() : nullptr;
    if (!map || !map->getBoolProperty("nativeCombatFacts")) {
        return;
    }
    auto context = game->getContext();
    batch = context ? context->nativeCombatBatch : nullptr;
    if (!current() || batch->depth == 0) {
        batch.reset();
    }
}

bool CNativeCombatFacts::current() const { return batch && batch->owns(cause, victim); }

void CNativeCombatFacts::capture(std::shared_ptr<const CNativeCombatFact> fact) const {
    if (!current()) {
        return;
    }
    if (batch->facts.size() >= CNativeCombatBatch::MAX_FACTS) {
        batch->overflow = true;
        return;
    }
    batch->facts.push_back(std::move(fact));
}

void CNativeCombatFacts::attempt(std::shared_ptr<CGameObject> producer) const {
    if (current()) {
        capture(std::make_shared<const CNativeCombatFact>(CNativeCombatFact{CGameEvent::CType::onCombatAttempt,
                                                                            cause,
                                                                            victim,
                                                                            std::move(producer),
                                                                            false,
                                                                            0,
                                                                            {},
                                                                            0,
                                                                            0,
                                                                            cause->getMana()}));
    }
}

void CNativeCombatFacts::roll(bool connected, int damage) const {
    if (current()) {
        capture(std::make_shared<const CNativeCombatFact>(
            CNativeCombatFact{CGameEvent::CType::onCombatRoll, cause, victim, nullptr, connected, damage}));
    }
}

void CNativeCombatFacts::packet(const DamageValue &damage, int hpBefore, int hpAfter,
                                std::shared_ptr<CGameObject> producer) const {
    if (current()) {
        capture(std::make_shared<const CNativeCombatFact>(CNativeCombatFact{CGameEvent::CType::onCombatPacket, cause,
                                                                            victim, std::move(producer), false, 0,
                                                                            damage, hpBefore, hpAfter}));
    }
}
