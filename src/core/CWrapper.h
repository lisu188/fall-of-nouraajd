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

#include "core/CConcepts.h"
#include "core/CGlobal.h"
#include "core/CPlugin.h"
#include "object/CDialog.h"
#include "object/CObject.h"

namespace py = pybind11;

template <fn::PythonWrapperBase T> class CWrapper : public T {
    V_META(CWrapper<T>, T, vstd::meta::empty())

  public:
    using T::T;

    void onEnter(std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, T, onEnter, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }

    void onTurn(std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, T, onTurn, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }

    void onCreate(std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, T, onCreate, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }

    void onDestroy(std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, T, onDestroy, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }

    void onLeave(std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, T, onLeave, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }
};

template <> class CWrapper<CInteraction> : public CInteraction {
    V_META(CWrapper<T>, CInteraction, vstd::meta::empty())

  public:
    using CInteraction::CInteraction;

    void performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) override final {
        try {
            PYBIND11_OVERRIDE(void, CInteraction, performAction, first, second);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }

    bool configureEffect(std::shared_ptr<CEffect> effect) override final {
        try {
            PYBIND11_OVERRIDE(bool, CInteraction, configureEffect, effect);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
            return false;
        }
    }
};

template <> class CWrapper<CEffect> : public CEffect {
    V_META(CWrapper<T>, CEffect, vstd::meta::empty())

  public:
    using CEffect::CEffect;

    void onEffect() override final {
        try {
            PYBIND11_OVERRIDE(void, CEffect, onEffect);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }
};

template <> class CWrapper<CTile> : public CTile {
    V_META(CWrapper<T>, CTile, vstd::meta::empty())

  public:
    using CTile::CTile;

    void onStep(std::shared_ptr<CCreature> creature) override final {
        try {
            PYBIND11_OVERRIDE(void, CTile, onStep, creature);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }
};

template <> class CWrapper<CPotion> : public CPotion {
    V_META(CWrapper<T>, CPotion, vstd::meta::empty())

  public:
    using CPotion::CPotion;

    void onUse(std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, CPotion, onUse, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }
};

template <> class CWrapper<CScroll> : public CScroll {
    V_META(CWrapper<T>, CScroll, vstd::meta::empty())

  public:
    using CScroll::CScroll;

    void onUse(std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, CScroll, onUse, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }

    bool isDisposable() override final {
        try {
            PYBIND11_OVERRIDE(bool, CScroll, isDisposable);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
            return false;
        }
    }
};

template <> class CWrapper<CTrigger> : public CTrigger {
    V_META(CWrapper<T>, CTrigger, vstd::meta::empty())

  public:
    using CTrigger::CTrigger;

    void trigger(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) override final {
        try {
            PYBIND11_OVERRIDE(void, CTrigger, trigger, object, event);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }
};

template <> class CWrapper<CQuest> : public CQuest {
    V_META(CWrapper<T>, CQuest, vstd::meta::empty())

  public:
    using CQuest::CQuest;

    bool isCompleted() override final {
        try {
            PYBIND11_OVERRIDE(bool, CQuest, isCompleted);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
            return false;
        }
    }

    void onComplete() override final {
        try {
            PYBIND11_OVERRIDE(void, CQuest, onComplete);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }
};

template <> class CWrapper<CPlugin> : public CPlugin {
    V_META(CWrapper<T>, CPlugin, vstd::meta::empty())

  public:
    using CPlugin::CPlugin;

    void load(std::shared_ptr<CGame> game) override final {
        try {
            PYBIND11_OVERRIDE(void, CPlugin, load, game);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }
};

template <> class CWrapper<CDialog> : public CDialog {
    V_META(CWrapper<T>, CDialog, vstd::meta::empty())

  public:
    using CDialog::CDialog;

    void invokeAction(std::string action) override final {
        try {
            PYBIND11_OVERRIDE(void, CDialog, invokeAction, action);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
        }
    }

    bool invokeCondition(std::string condition) override final {
        try {
            PYBIND11_OVERRIDE(bool, CDialog, invokeCondition, condition);
        } catch (const py::error_already_set &) {
            PYTHON_LOG;
            PyErr_Clear();
            return true;
        }
    }
};
