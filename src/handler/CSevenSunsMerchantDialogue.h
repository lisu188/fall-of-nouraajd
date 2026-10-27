// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "core/CExport.h"
#include "core/CGlobal.h"
#include <cstdint>
#include <functional>
#include <memory>
#include <string>

class CCreature;
class CGame;
class CGameObject;
class CMap;

// Native finite authority, reachable only through the private UI-flow dispatcher.
class GAME_CORE_EXPORT CSevenSunsMerchantDialogue {
  public:
    static bool isSupported();
    static std::unique_ptr<CSevenSunsMerchantDialogue> begin(std::weak_ptr<CGame> game,
                                                             std::shared_ptr<CGameObject> clock,
                                                             std::shared_ptr<CCreature> actor,
                                                             std::function<void()> requireCaller);
    static json settle(std::weak_ptr<CGame> game, std::shared_ptr<CGameObject> clock,
                       std::function<void()> requireCaller);
    ~CSevenSunsMerchantDialogue();
    CSevenSunsMerchantDialogue(const CSevenSunsMerchantDialogue &) = delete;
    CSevenSunsMerchantDialogue &operator=(const CSevenSunsMerchantDialogue &) = delete;
    json view() const;
    void requireCurrent() const;
    json advance(int revision, int edgeIndex);
    json close();

  private:
    friend class CGuiHandler;
    friend class CFightHandler;
    static bool isSettledReplacement(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                     const std::shared_ptr<CCreature> &actor,
                                     const std::function<void()> &requireCurrent);
    struct State;
    explicit CSevenSunsMerchantDialogue(std::unique_ptr<State> state);
    CSevenSunsMerchantDialogue(std::string refusal, std::string lineage, int count, int revision);
    static int readInteger(const json &value);
    static bool combatOwned(const std::shared_ptr<CCreature> &actor);
    static std::uint64_t regionEpoch(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map);
    static bool retired(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                        const std::shared_ptr<CCreature> &actor);
    static bool hasLifetimeOwner(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                 const std::shared_ptr<CCreature> &actor);
    static bool unowned(const std::shared_ptr<CGame> &game, const std::shared_ptr<CCreature> &actor);
    static void publish(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                        const std::shared_ptr<CCreature> &oldActor, const std::shared_ptr<CCreature> &newActor,
                        const std::function<void()> &requireCurrent);
    std::unique_ptr<State> state;
    std::string refusal;
    std::string refusedLineage;
    int refusedCount = 0;
    int refusedRevision = 0;
};
