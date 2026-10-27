// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "core/CExport.h"
#include "core/CGlobal.h"
#include <functional>
#include <memory>

class CCreature;
class CGame;
class CGameObject;
class CMap;

// Finite native authority owned by one UI flow; never exposed as a Python mutation object.
class GAME_CORE_EXPORT CSevenSunsDialogue {
  public:
    static std::unique_ptr<CSevenSunsDialogue> begin(std::weak_ptr<CGame> game, std::shared_ptr<CGameObject> clock,
                                                     std::shared_ptr<CCreature> actor,
                                                     std::function<void()> requireCaller);
    ~CSevenSunsDialogue();
    CSevenSunsDialogue(const CSevenSunsDialogue &) = delete;
    CSevenSunsDialogue &operator=(const CSevenSunsDialogue &) = delete;
    json view() const;
    void requireCurrent() const;
    json advance(int revision, int edgeIndex);
    json close();

  private:
    friend class CGuiHandler;
    static int readInteger(const json &value);
    static bool hasSceneLifetimeOwner(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                      const std::shared_ptr<CCreature> &actor, bool requireDetached);
    struct State;
    explicit CSevenSunsDialogue(std::unique_ptr<State> state);
    std::unique_ptr<State> state;
};
