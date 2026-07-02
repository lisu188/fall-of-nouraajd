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

#include <memory>
#include <optional>
#include <string>

#include "core/CUtil.h"

class CGame;
class CGameContext;

// Opt-in description of a single map transition. The legacy CGame::changeMap(std::string) path is
// equivalent to a request with only targetMap set: the destination is reloaded from content, the
// source map is not retained, the player lands at the destination entry, and the turn carries over.
// The remaining fields opt into persistent map sessions backed by CMapSessionStore without changing
// behavior for existing map scripts.
struct CMapTransitionRequest {
    // Destination map name (a map directory under res/maps).
    std::string targetMap;
    // Player placement on the destination map; std::nullopt places the player at the map entry.
    std::optional<Coords> targetCoords;
    // Reuse an already-loaded destination session from CMapSessionStore instead of reloading it
    // from content. Falls back to a fresh load when no matching session is stored.
    bool reuseLoadedMap = false;
    // Retain the source map in CMapSessionStore when leaving it, so it can be revisited later.
    bool retainSourceMap = false;
    // Optional session anchor: a retained source session is stored under this instance id, and a
    // reuseLoadedMap lookup prefers this instance id before falling back to the default session.
    std::string returnAnchor;
    // Copy the source map turn onto the destination (legacy behavior). Persistent sessions can keep
    // their own turn counter by disabling this.
    bool carryTurn = true;
};

class CSceneManager : public std::enable_shared_from_this<CSceneManager> {
    friend class CGameContext;

  public:
    enum class TransitionState { Idle, TransitionPending, Transitioning };

    using MapTransitionRequest = CMapTransitionRequest;

    bool requestMapChange(const std::shared_ptr<CGame> &game, std::string mapName);

    bool requestMapChange(const std::shared_ptr<CGame> &game, CMapTransitionRequest request);

    bool isTransitionPending() const;

    TransitionState getTransitionState() const;

    std::string getTransitionStateName() const;

    std::string getPendingMapName() const;

  private:
    void performMapChange(const std::shared_ptr<CGame> &game, const CMapTransitionRequest &request);

    void resetTransition();

    TransitionState transitionState = TransitionState::Idle;
    std::string pendingMapName;
};
