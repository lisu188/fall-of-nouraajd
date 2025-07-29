/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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

#include "core/CGlobal.h"
#include "core/CUtil.h"
#include "object/CObject.h"

class CMap;

class CTrigger;

class CGameObject;

class CGameEvent : public CGameObject {
  V_META(CGameEvent, CGameObject, vstd::meta::empty())
public:
  class Type {
  public:
    static std::string onEnter;
    static std::string onTurn;
    static std::string onCreate;
    static std::string onDestroy;
    static std::string onLeave;
    static std::string onUse;
    static std::string onEquip;
    static std::string onUnequip;
    static std::string inventoryChanged;
    static std::string equippedChanged;
  };

  CGameEvent();

  CGameEvent(std::string type);

  std::string getType() const;

private:
  const std::string type;
};

class CGameEventCaused : public CGameEvent {
  V_META(CGameEventCaused, CGameEvent, vstd::meta::empty())
public:
  CGameEventCaused();

  CGameEventCaused(std::string type, std::shared_ptr<CGameObject> cause);

  std::shared_ptr<CGameObject> getCause() const;

private:
  std::shared_ptr<CGameObject> cause;
};

class CEventHandler : public CGameObject {
  typedef std::unordered_multimap<std::pair<std::string, std::string>,
                                  std::shared_ptr<CTrigger>>
      TriggerMap;

public:
  void gameEvent(std::shared_ptr<CMapObject> mapObject,
                 std::shared_ptr<CGameEvent> event) const;

  void registerTrigger(std::shared_ptr<CTrigger> trigger);

  std::set<std::shared_ptr<CTrigger>> getTriggers();

private:
  TriggerMap triggers;
};
