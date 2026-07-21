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

#include "handler/CLuaHandler.h"
#include "object/CObject.h"

// Lua counterparts of the CWrapper<T> pybind trampolines: each scriptable base gets a subclass
// whose overridable virtuals first offer the call to the object's registered Lua hook table
// (CLuaHandler::dispatch — false means "no hook", so the base implementation runs, exactly like
// PYBIND11_OVERRIDE's fallback). Instances are produced only by the factories that
// CLuaHandler's registerType installs, which retain them in CLuaOverrides.

template <typename T> class CLuaWrapper;

template <> class CLuaWrapper<CTile> : public CTile {
    V_META(CLuaWrapper<CTile>, CTile, vstd::meta::empty())

  public:
    using CTile::CTile;

    void onStep(std::shared_ptr<CCreature> creature) override final {
        if (CLuaHandler::dispatch(this, "onStep", {creature})) {
            return;
        }
        CTile::onStep(creature);
    }
};

template <> class CLuaWrapper<CEffect> : public CEffect {
    V_META(CLuaWrapper<CEffect>, CEffect, vstd::meta::empty())

  public:
    using CEffect::CEffect;

    void onEffect() override final {
        if (CLuaHandler::dispatch(this, "onEffect")) {
            return;
        }
        CEffect::onEffect();
    }
};

template <> class CLuaWrapper<CPotion> : public CPotion {
    V_META(CLuaWrapper<CPotion>, CPotion, vstd::meta::empty())

  public:
    using CPotion::CPotion;

    void onUse(std::shared_ptr<CGameEvent> event) override final {
        if (CLuaHandler::dispatch(this, "onUse", {event})) {
            return;
        }
        CPotion::onUse(event);
    }
};

template <> class CLuaWrapper<CScroll> : public CScroll {
    V_META(CLuaWrapper<CScroll>, CScroll, vstd::meta::empty())

  public:
    using CScroll::CScroll;

    void onUse(std::shared_ptr<CGameEvent> event) override final {
        if (CLuaHandler::dispatch(this, "onUse", {event})) {
            return;
        }
        CScroll::onUse(event);
    }

    bool isDisposable() override final {
        bool result = false;
        if (CLuaHandler::dispatchBool(this, "isDisposable", {}, result)) {
            return result;
        }
        return CScroll::isDisposable();
    }
};

template <> class CLuaWrapper<CInteraction> : public CInteraction {
    V_META(CLuaWrapper<CInteraction>, CInteraction, vstd::meta::empty())

  public:
    using CInteraction::CInteraction;

    void performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) override final {
        if (CLuaHandler::dispatch(this, "performAction", {first, second})) {
            return;
        }
        CInteraction::performAction(first, second);
    }

    bool configureEffect(std::shared_ptr<CEffect> effect) override final {
        bool result = false;
        if (CLuaHandler::dispatchBool(this, "configureEffect", {effect}, result)) {
            return result;
        }
        return CInteraction::configureEffect(effect);
    }
};

template <> class CLuaWrapper<CTrigger> : public CTrigger {
    V_META(CLuaWrapper<CTrigger>, CTrigger, vstd::meta::empty())

  public:
    using CTrigger::CTrigger;

    void trigger(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) override final {
        if (CLuaHandler::dispatch(this, "trigger", {object, event})) {
            return;
        }
        CTrigger::trigger(object, event);
    }
};

// Map-object lifecycle trampoline shared by the bases whose scripting surface is the five
// CGameEvent hooks — the Lua counterpart of the generic CWrapper<T>.
#define CLUAWRAPPER_LIFECYCLE_TRAMPOLINE(BASE)                                                                         \
    template <> class CLuaWrapper<BASE> : public BASE {                                                                \
        V_META(CLuaWrapper<BASE>, BASE, vstd::meta::empty())                                                           \
      public:                                                                                                          \
        using BASE::BASE;                                                                                              \
        void onEnter(std::shared_ptr<CGameEvent> event) override final {                                               \
            if (CLuaHandler::dispatch(this, "onEnter", {event})) {                                                     \
                return;                                                                                                \
            }                                                                                                          \
            BASE::onEnter(event);                                                                                      \
        }                                                                                                              \
        void onLeave(std::shared_ptr<CGameEvent> event) override final {                                               \
            if (CLuaHandler::dispatch(this, "onLeave", {event})) {                                                     \
                return;                                                                                                \
            }                                                                                                          \
            BASE::onLeave(event);                                                                                      \
        }                                                                                                              \
        void onTurn(std::shared_ptr<CGameEvent> event) override final {                                                \
            if (CLuaHandler::dispatch(this, "onTurn", {event})) {                                                      \
                return;                                                                                                \
            }                                                                                                          \
            BASE::onTurn(event);                                                                                       \
        }                                                                                                              \
        void onCreate(std::shared_ptr<CGameEvent> event) override final {                                              \
            if (CLuaHandler::dispatch(this, "onCreate", {event})) {                                                    \
                return;                                                                                                \
            }                                                                                                          \
            BASE::onCreate(event);                                                                                     \
        }                                                                                                              \
        void onDestroy(std::shared_ptr<CGameEvent> event) override final {                                             \
            if (CLuaHandler::dispatch(this, "onDestroy", {event})) {                                                   \
                return;                                                                                                \
            }                                                                                                          \
            BASE::onDestroy(event);                                                                                    \
        }                                                                                                              \
    };

CLUAWRAPPER_LIFECYCLE_TRAMPOLINE(CBuilding)
CLUAWRAPPER_LIFECYCLE_TRAMPOLINE(CEvent)
#undef CLUAWRAPPER_LIFECYCLE_TRAMPOLINE
