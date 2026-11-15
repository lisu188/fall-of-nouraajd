// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "core/CExport.h"
#include "core/CGlobal.h"
#include <array>
#include <functional>
#include <memory>
#include <string>
#include <vector>

class CCreature;
class CGame;
class CItem;
class CTargetController;
class CMonsterFightController;
class CInteraction;

class GAME_CORE_EXPORT CSevenSunsMerchantStock {
  public:
    struct Prepared {
        std::shared_ptr<CCreature> actor;
        json receipt;
        std::vector<std::shared_ptr<CItem>> owned;
        std::shared_ptr<CTargetController> controller;
        std::shared_ptr<CMonsterFightController> fightController;
        std::shared_ptr<CInteraction> attack;
    };

    static bool isSupported();
    static Prepared prepare(const std::shared_ptr<CGame> &game, const std::string &lineage, const std::string &area,
                            const std::function<void()> &requireCurrent);
    static void validatePrepared(const Prepared &prepared, const std::shared_ptr<CGame> &game,
                                 const std::string &lineage, const std::string &area,
                                 const std::function<void()> &requireCurrent);
    static void validateSettled(const std::shared_ptr<CCreature> &actor, const json &receipt,
                                const std::shared_ptr<CGame> &game, const std::string &lineage, const std::string &area,
                                const std::function<void()> &requireCurrent);
    static json resolveRollsForTests(const std::array<int, 3> &rolls);
};
