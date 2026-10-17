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
#pragma once

#include "CGameObject.h"

class CTrigger : public CGameObject {
    V_META(CTrigger, CGameObject, V_PROPERTY(CTrigger, std::string, object, getObject, setObject),
           V_PROPERTY(CTrigger, std::string, event, getEvent, setEvent))
  public:
    CTrigger();

    virtual void trigger(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>);

    virtual vstd::task<void> triggerAsync(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event);

  private:
    std::string object;
    std::string event;

  public:
    std::string getObject();

    void setObject(std::string object);

    std::string getEvent();

    void setEvent(std::string event);
};

class CCustomTrigger : public CTrigger {
    V_META(CCustomTrigger, CTrigger, vstd::meta::empty())

    std::function<void(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>)> _trigger;
    std::function<vstd::task<void>(std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>)> _triggerAsync;

  public:
    template <fn::TriggerCallback T> CCustomTrigger(std::string object, std::string event, T __trigger) {
        if constexpr (std::same_as<std::invoke_result_t<T &, std::shared_ptr<CGameObject>, std::shared_ptr<CGameEvent>>,
                                   vstd::task<void>>) {
            _triggerAsync = std::move(__trigger);
        } else {
            _trigger = std::move(__trigger);
        }
        setObject(object);
        setEvent(event);
    }

    void trigger(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) override;

    vstd::task<void> triggerAsync(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) override;
};
