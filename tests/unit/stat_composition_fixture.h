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
#pragma once

#include "core/CStats.h"
#include "object/CCreature.h"
#include "object/CCreatureClass.h"
#include "object/CCreatureClassTrack.h"
#include "object/CCreatureRace.h"
#include "object/CCreatureTemplate.h"
#include "object/CEffect.h"
#include "object/CItem.h"

#include <array>
#include <memory>
#include <string>
#include <vector>

namespace performance_guard {
void resetNumericIncrementProbe();
std::size_t numericIncrementProbeCount();
void disableNumericIncrementProbe();
} // namespace performance_guard

namespace stat_composition_fixture {

inline const std::array<std::string, 17> fieldNames{
    "strength",    "agility",      "stamina",       "intelligence", "armor", "block",
    "dmgMin",      "dmgMax",       "attack",        "hit",          "crit",  "fireResist",
    "frostResist", "normalResist", "thunderResist", "shadowResist", "damage"};

class IncrementProbe {
  public:
    IncrementProbe() { performance_guard::resetNumericIncrementProbe(); }
    ~IncrementProbe() { performance_guard::disableNumericIncrementProbe(); }
    IncrementProbe(const IncrementProbe &) = delete;
    IncrementProbe &operator=(const IncrementProbe &) = delete;
    std::size_t count() const { return performance_guard::numericIncrementProbeCount(); }
};

struct Fixture {
    std::shared_ptr<CCreature> creature = std::make_shared<CCreature>();
    std::vector<std::shared_ptr<CStats>> sources;

    std::shared_ptr<CStats> source() {
        auto stats = std::make_shared<CStats>();
        const int ordinal = static_cast<int>(sources.size());
        for (std::size_t i = 0; i < fieldNames.size(); ++i) {
            stats->setNumericProperty(fieldNames[i], (ordinal * 3 + static_cast<int>(i) * 5) % 11 - 5);
        }
        stats->setMainStat("stamina");
        sources.push_back(stats);
        return stats;
    }
};

// Modes: legacy, race-only, class-only, template-only, tracks-only, full multiclass,
// full single class. Every source includes positive, negative and zero fields.
inline Fixture make(int mode) {
    Fixture fixture;
    auto creature = fixture.creature;
    creature->setBaseStats(fixture.source());
    creature->setLevelStats(fixture.source());
    creature->setLevel(3);
    creature->setRacialLevel(2);
    if (mode == 1 || mode >= 5) {
        auto race = std::make_shared<CCreatureRace>();
        race->setBaseStats(fixture.source());
        race->setRacialLevelStats(fixture.source());
        creature->setRace(race);
    }
    if (mode == 2 || mode >= 4) {
        auto klass = std::make_shared<CCreatureClass>();
        klass->setBaseStats(fixture.source());
        klass->setLevelStats(fixture.source());
        klass->setMainStat("intelligence");
        creature->setCreatureClass(klass);
        if (mode == 4 || mode == 5) {
            auto later_class = std::make_shared<CCreatureClass>();
            later_class->setBaseStats(fixture.source());
            later_class->setLevelStats(fixture.source());
            later_class->setMainStat("strength");
            auto first = std::make_shared<CCreatureClassTrack>();
            first->setOrder(10);
            first->setLevel(2);
            first->setCreatureClass(klass);
            auto later = std::make_shared<CCreatureClassTrack>();
            later->setOrder(20);
            later->setLevel(4);
            later->setCreatureClass(later_class);
            auto empty = std::make_shared<CCreatureClassTrack>();
            empty->setOrder(0);
            creature->setClassTracks({later, nullptr, empty, first});
        }
    }
    if (mode == 3 || mode >= 5) {
        auto first = std::make_shared<CCreatureTemplate>();
        first->setOrder(10);
        first->setStatAdjustments(fixture.source());
        auto later = std::make_shared<CCreatureTemplate>();
        later->setOrder(20);
        later->setStatAdjustments(fixture.source());
        creature->setTemplates({later, nullptr, first});
    }
    auto item = std::make_shared<CItem>();
    item->setBonus(fixture.source());
    auto other_item = std::make_shared<CItem>();
    other_item->setBonus(fixture.source());
    creature->setEquipped({{"0", item}, {"1", nullptr}, {"2", other_item}});
    auto effect = std::make_shared<CEffect>();
    effect->setBonus(fixture.source());
    effect->setDuration(4);
    creature->setEffects({effect});
    // addBonus always reads source typed members, even when a dynamic shadow exists.
    fixture.sources.front()->meta()->set_dynamic_property("strength", fixture.sources.front(), 900);
    return fixture;
}

// Independent reference retains the old reflective contribution sequence. Never
// use the optimized destination fold or multiply growth into one contribution.
inline std::shared_ptr<CStats> reflectiveReference(const std::shared_ptr<CCreature> &creature,
                                                   std::size_t &contributions) {
    auto result = std::make_shared<CStats>();
    contributions = 0;
    auto add = [&](const std::shared_ptr<CStats> &source) {
        result->addBonus(source);
        ++contributions;
    };
    const auto race = creature->getRace();
    const auto klass = creature->getCreatureClass();
    const auto tracks = creature->getOrderedClassTracks();
    std::string main_stat = creature->getBaseStats()->getMainStat();
    if (!tracks.empty()) {
        for (const auto &track : tracks) {
            auto track_class = track->getCreatureClass();
            if (track_class && !track_class->getMainStat().empty()) {
                main_stat = track_class->getMainStat();
                break;
            }
        }
    } else if (klass && !klass->getMainStat().empty()) {
        main_stat = klass->getMainStat();
    }
    result->setMainStat(main_stat);
    if (creature->usesArchetypeComposition()) {
        if (race && race->getBaseStats()) {
            add(race->getBaseStats());
        }
        if (!tracks.empty()) {
            for (const auto &track : tracks) {
                auto track_class = track->getCreatureClass();
                if (track_class && track_class->getBaseStats()) {
                    add(track_class->getBaseStats());
                }
            }
        } else if (klass && klass->getBaseStats()) {
            add(klass->getBaseStats());
        }
    }
    add(creature->getBaseStats());
    if (creature->usesArchetypeComposition()) {
        if (race && race->getRacialLevelStats()) {
            for (int i = 0; i < creature->getRacialLevel(); ++i) {
                add(race->getRacialLevelStats());
            }
        }
        if (!tracks.empty()) {
            for (const auto &track : tracks) {
                auto track_class = track->getCreatureClass();
                if (track_class && track_class->getLevelStats()) {
                    for (int i = 0; i < track->getLevel(); ++i) {
                        add(track_class->getLevelStats());
                    }
                }
            }
        } else if (klass && klass->getLevelStats()) {
            for (int i = 0; i < creature->getLevel(); ++i) {
                add(klass->getLevelStats());
            }
        }
    }
    for (int i = 0; i < creature->getLevel(); ++i) {
        add(creature->getLevelStats());
    }
    if (creature->usesArchetypeComposition()) {
        for (const auto &overlay : creature->getOrderedTemplates()) {
            if (overlay->getStatAdjustments()) {
                add(overlay->getStatAdjustments());
            }
        }
    }
    for (auto [slot, item] : creature->getEquipped()) {
        if (item) {
            add(item->getBonus());
        }
    }
    for (auto effect : creature->getEffects()) {
        if (effect) {
            add(effect->getBonus());
        }
    }
    return result;
}
} // namespace stat_composition_fixture
