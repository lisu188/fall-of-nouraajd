/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2020  Andrzej Lis

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
#include "core/CPlugin.h"
#include "object/CObject.h"
#include "object/CDialog.h"

template<class T>
class CWrapper : public T, public boost::python::wrapper<CWrapper<T>> {
V_META(CWrapper<T>, T, vstd::meta::empty())
public:
    virtual void onEnter(std::shared_ptr<CGameEvent> event) override final {
        if (auto f = this->get_override("onEnter")) {
            PY_SAFE (f(event))
        } else {
            this->T::onEnter(event);
        }
    }

    virtual void onTurn(std::shared_ptr<CGameEvent> event) override final {
        if (auto f = this->get_override("onTurn")) {
            PY_SAFE (f(event))
        } else {
            this->T::onTurn(event);
        }
    }

    virtual void onCreate(std::shared_ptr<CGameEvent> event) override final {
        if (auto f = this->get_override("onCreate")) {
            PY_SAFE (f(event))
        } else {
            this->T::onCreate(event);
        }
    }

    virtual void onDestroy(std::shared_ptr<CGameEvent> event) override final {
        if (auto f = this->get_override("onDestroy")) {
            PY_SAFE (f(event))
        } else {
            this->T::onDestroy(event);
        }
    }

    virtual void onLeave(std::shared_ptr<CGameEvent> event) override final {
        if (auto f = this->get_override("onLeave")) {
            PY_SAFE (f(event))
        } else {
            this->T::onLeave(event);
        }
    }
};

template<>
class CWrapper<CInteraction> : public CInteraction, public boost::python::wrapper<CWrapper<CInteraction>> {
V_META(CWrapper<T>, CInteraction, vstd::meta::empty())
public:
    void performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) override final {
        if (auto f = this->get_override("performAction")) {
            PY_SAFE (f(first, second))
        } else {
            this->CInteraction::performAction(first, second);
        }
    }

    bool configureEffect(std::shared_ptr<CEffect> effect) override final {
        if (auto f = this->get_override("configureEffect")) {
            PY_SAFE_RET_VAL (return f(effect), false)
        } else {
            return this->CInteraction::configureEffect(effect);
        }
    }
};

template<>
class CWrapper<CEffect> : public CEffect, public boost::python::wrapper<CWrapper<CEffect>> {
V_META(CWrapper<T>, CEffect, vstd::meta::empty())
public:
    void onEffect() override final {
        if (auto f = this->get_override("onEffect")) {
            PY_SAFE (f())
        } else {
            this->CEffect::onEffect();
        }
    }

};

template<>
class CWrapper<CTile> : public CTile, public boost::python::wrapper<CWrapper<CTile>> {
V_META(CWrapper<T>, CTile, vstd::meta::empty())
public:
    void onStep(std::shared_ptr<CCreature> creature) override final {
        if (auto f = this->get_override("onStep")) {
            PY_SAFE (f(creature))
        } else {
            this->CTile::onStep(creature);
        }
    }

};

template<>
class CWrapper<CPotion> : public CPotion, public boost::python::wrapper<CWrapper<CPotion>> {
V_META(CWrapper<T>, CPotion, vstd::meta::empty())
public:
    void onUse(std::shared_ptr<CGameEvent> event) override final {
        if (auto f = this->get_override("onUse")) {
            PY_SAFE (f(event))
        } else {
            this->CPotion::onUse(event);
        }
    }
};

template<>
class CWrapper<CTrigger> : public CTrigger, public boost::python::wrapper<CWrapper<CTrigger>> {
V_META(CWrapper<T>, CTrigger, vstd::meta::empty())
public:
    void trigger(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) override final {
        if (auto f = this->get_override("trigger")) {
            PY_SAFE (f(object, event))
        } else {
            this->CTrigger::trigger(object, event);
        }
    }
};

template<>
class CWrapper<CQuest> : public CQuest, public boost::python::wrapper<CWrapper<CQuest>> {
V_META(CWrapper<T>, CQuest, vstd::meta::empty())
public:
    bool isCompleted() override final {
        if (auto f = this->get_override("isCompleted")) {
            PY_SAFE_RET_VAL (return f();, false)
        } else {
            return this->CQuest::isCompleted();
        }
    }

    void onComplete() override final {
        if (auto f = this->get_override("onComplete")) {
            PY_SAFE (f())
        } else {
            this->CQuest::onComplete();
        }
    }
};

template<>
class CWrapper<CPlugin> : public CPlugin, public boost::python::wrapper<CWrapper<CPlugin>> {
V_META(CWrapper<T>, CPlugin, vstd::meta::empty())
public:
    void load(std::shared_ptr<CGame> game) override final {
        if (auto f = this->get_override("load")) {
            PY_SAFE (f(game))
        } else {
            this->CPlugin::load(game);
        }
    }
};

template<>
class CWrapper<CDialog> : public CDialog, public boost::python::wrapper<CWrapper<CDialog>> {
V_META(CWrapper<T>, CDialog, vstd::meta::empty())
};