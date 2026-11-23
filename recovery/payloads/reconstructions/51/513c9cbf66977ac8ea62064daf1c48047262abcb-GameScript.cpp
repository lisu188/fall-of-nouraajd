// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
// Historical reconstruction; original bytes are unavailable. See the recovery
// provenance.
#include "CBuilding.h"
#include "CCreature.h"
#include "CGuiHandler.h"
#include "CInteraction.h"
#include "CItem.h"
#include "CMap.h"
#include "CMapObject.h"
#include "CTile.h"
#include "Stats.h"
#include "Util.h"
#include <Python.h>
#include <QByteArray>
#include <QString>
#include <boost/python.hpp>
#include <boost/shared_ptr.hpp>
#include <utility>

using namespace boost::python;

struct QStringToPython {
  static PyObject *convert(const QString &value) {
    QByteArray bytes = value.toUtf8();
    return PyUnicode_DecodeUTF8(bytes.constData(), bytes.size(), "strict");
  }
};

struct QStringFromPython {
  QStringFromPython() {
    converter::registry::push_back(&convertible, &construct,
                                   type_id<QString>());
  }
  static void *convertible(PyObject *value) {
    return PyBytes_Check(value) || PyUnicode_Check(value) ? value : 0;
  }
  static void construct(PyObject *value,
                        converter::rvalue_from_python_stage1_data *data) {
    handle<> encoded;
    if (PyUnicode_Check(value)) {
      encoded = handle<>(PyUnicode_AsUTF8String(value));
      value = encoded.get();
    }
    char *bytes = 0;
    Py_ssize_t size = 0;
    if (PyBytes_AsStringAndSize(value, &bytes, &size) == -1) {
      throw_error_already_set();
    }
    void *storage =
        reinterpret_cast<converter::rvalue_from_python_storage<QString> *>(data)
            ->storage.bytes;
    new (storage) QString(QString::fromUtf8(bytes, size));
    data->convertible = storage;
  }
};

template <class T> class CWrapper : public T, public wrapper<CWrapper<T>> {
public:
  void onEnter() override {
    if (override call = this->get_override("onEnter")) {
      call();
    } else {
      T::onEnter();
    }
  }
  void onMove() override {
    if (override call = this->get_override("onMove")) {
      call();
    } else {
      T::onMove();
    }
  }
  void onCreate() override {
    if (override call = this->get_override("onCreate")) {
      call();
    } else {
      T::onCreate();
    }
  }
  void onDestroy() override {
    if (override call = this->get_override("onDestroy")) {
      call();
    } else {
      T::onDestroy();
    }
  }
  void defaultOnEnter() { T::onEnter(); }
  void defaultOnMove() { T::onMove(); }
  void defaultOnCreate() { T::onCreate(); }
  void defaultOnDestroy() { T::onDestroy(); }
};

class CInteractionWrapper : public CInteraction,
                            public wrapper<CInteractionWrapper> {
public:
  void performAction(CCreature *first, CCreature *second) override {
    if (override call = get_override("performAction")) {
      call(boost::ref(first), boost::ref(second));
    } else {
      CInteraction::performAction(first, second);
    }
  }
  bool configureEffect(CEffect *effect) override {
    if (override call = get_override("configureEffect")) {
      return call(boost::ref(effect));
    }
    return CInteraction::configureEffect(effect);
  }
  void defaultPerformAction(CCreature *first, CCreature *second) {
    CInteraction::performAction(first, second);
  }
  bool defaultConfigureEffect(CEffect *effect) {
    return CInteraction::configureEffect(effect);
  }
};

template <class Result> struct PythonPotionCall {
  static Result call(override function, CCreature *creature) {
    return function(boost::ref(creature)).template as<Result>();
  }
};

template <> struct PythonPotionCall<void> {
  static void call(override function, CCreature *creature) {
    function(boost::ref(creature));
  }
};

class CPotionWrapper : public CPotion, public wrapper<CPotionWrapper> {
public:
  // The unchanged original module blob spans the native void-to-bool onUse
  // transition.
  using Result =
      decltype(std::declval<CPotion &>().onUse(static_cast<CCreature *>(0)));
  Result onUse(CCreature *creature) override {
    if (override function = get_override("onUse")) {
      return PythonPotionCall<Result>::call(function, creature);
    }
    return CPotion::onUse(creature);
  }
  Result defaultOnUse(CCreature *creature) { return CPotion::onUse(creature); }
};

static void moveObject(CMapObject &value, int x, int y, int z) {
  value.moveTo(x, y, z);
}

static QString objectName(const CMapObject &value) {
  return value.objectName();
}
static void setObjectName(CMapObject &value, QString name) {
  value.setObjectName(name);
}

template <class T> static void registerObjectCallbacks(const char *name) {
  class_<CWrapper<T>, bases<T>, boost::noncopyable,
         boost::shared_ptr<CWrapper<T>>>(name)
      .def("onEnter", &T::onEnter, &CWrapper<T>::defaultOnEnter)
      .def("onMove", &T::onMove, &CWrapper<T>::defaultOnMove)
      .def("onCreate", &T::onCreate, &CWrapper<T>::defaultOnCreate)
      .def("onDestroy", &T::onDestroy, &CWrapper<T>::defaultOnDestroy);
}

// Under Python 2.7, Boost exports the init_game symbol called by CScriptEngine.
BOOST_PYTHON_MODULE(_game) {
  to_python_converter<QString, QStringToPython>();
  QStringFromPython();
  class_<Coords>("Coords", init<int, int, int>())
      .def_readwrite("x", &Coords::x)
      .def_readwrite("y", &Coords::y)
      .def_readwrite("z", &Coords::z);
  class_<CGuiHandler, boost::noncopyable>("CGuiHandler", no_init)
      .def("showMessage", &CGuiHandler::showMessage);
  class_<CMap, boost::noncopyable>("CMap", no_init)
      .def("addObjectByName", &CMap::addObjectByName)
      .def("removeObjectByName", &CMap::removeObjectByName)
      .def("removeObject", &CMap::removeObject)
      .def("replaceTile", &CMap::replaceTile)
      .def("getPlayer", &CMap::getPlayer, return_internal_reference<>())
      .def("getGuiHandler", &CMap::getGuiHandler, return_internal_reference<>())
      .def("getObjectByName", &CMap::getObjectByName,
           return_internal_reference<>())
      .def("getLocationByName", &CMap::getLocationByName);
  class_<CMapObject, boost::noncopyable>("CMapObject", no_init)
      .add_property("name", &objectName, &setObjectName)
      .def("getMap", &CMapObject::getMap, return_internal_reference<>())
      .def("moveTo", &moveObject)
      .def("getCoords", &CMapObject::getCoords)
      .def("setCoords", &CMapObject::setCoords)
      .def("removeFromGame", &CMapObject::removeFromGame)
          PY_PROPERTY_ACCESSOR(CMapObject);
  class_<Stats>("Stats").def("getDamage", &Stats::getDamage)
      PY_PROPERTY_ACCESSOR(Stats);
  class_<Damage>("Damage") PY_PROPERTY_ACCESSOR(Damage);
  class_<CCreature, bases<CMapObject>, boost::noncopyable>("CCreature", no_init)
      .def("getDmg", &CCreature::getDmg)
      .def("hurt", static_cast<void (CCreature::*)(int)>(&CCreature::hurt))
      .def("hurt", static_cast<void (CCreature::*)(Damage)>(&CCreature::hurt))
      .def("getWeapon", &CCreature::getWeapon, return_internal_reference<>())
      .def("getArmor", &CCreature::getArmor, return_internal_reference<>())
      .def("getStats", &CCreature::getStats, return_internal_reference<>())
      .def("getHp", &CCreature::getHp)
      .def("getHpMax", &CCreature::getHpMax)
      .def("getHpRatio", &CCreature::getHpRatio)
      .def("getMana", &CCreature::getMana)
      .def("getManaMax", &CCreature::getManaMax)
      .def("getManaRatio", &CCreature::getManaRatio)
      .def("getLevel", &CCreature::getLevel)
      .def("heal", &CCreature::heal)
      .def("healProc", &CCreature::healProc)
      .def("addMana", &CCreature::addMana)
      .def("addManaProc", &CCreature::addManaProc)
      .def("takeMana", &CCreature::takeMana)
      .def("isAlive", &CCreature::isAlive)
      .def("isPlayer", &CCreature::isPlayer);
  class_<CPlayer, bases<CCreature>, boost::noncopyable>("CPlayer", no_init);
  class_<CMonster, bases<CCreature>, boost::noncopyable>("CMonster", no_init);
  class_<CBuilding, bases<CMapObject>, boost::noncopyable>("CBuildingBase");
  class_<CEvent, bases<CMapObject>, boost::noncopyable>("CEventBase");
  registerObjectCallbacks<CBuilding>("CBuilding");
  registerObjectCallbacks<CEvent>("CEvent");
  class_<CInteraction, bases<CMapObject>, boost::noncopyable>(
      "CInteractionBase")
      .def("onAction", &CInteraction::onAction);
  class_<CInteractionWrapper, bases<CInteraction>, boost::noncopyable,
         boost::shared_ptr<CInteractionWrapper>>("CInteraction")
      .def("performAction", &CInteraction::performAction,
           &CInteractionWrapper::defaultPerformAction)
      .def("configureEffect", &CInteraction::configureEffect,
           &CInteractionWrapper::defaultConfigureEffect);
  scope().attr("Interaction") = scope().attr("CInteraction");
  class_<CEffect, bases<CMapObject>, boost::noncopyable>("Effect", no_init)
      .def("getBonus", &CEffect::getBonus, return_internal_reference<>())
      .def("setBonus", &CEffect::setBonus)
      .def("getCaster", &CEffect::getCaster, return_internal_reference<>())
      .def("getVictim", &CEffect::getVictim, return_internal_reference<>())
      .def("getTimeLeft", &CEffect::getTimeLeft)
      .def("getTimeTotal", &CEffect::getTimeTotal);
  class_<CItem, bases<CMapObject>, boost::noncopyable>("CItem");
  class_<CArmor, bases<CItem>, boost::noncopyable>("CArmor");
  class_<CBelt, bases<CItem>, boost::noncopyable>("CBelt");
  class_<CHelmet, bases<CItem>, boost::noncopyable>("CHelmet");
  class_<CBoots, bases<CItem>, boost::noncopyable>("CBoots");
  class_<CGloves, bases<CItem>, boost::noncopyable>("CGloves");
  class_<CWeapon, bases<CItem>, boost::noncopyable>("CWeapon").def(
      "getInteraction", &CWeapon::getInteraction,
      return_internal_reference<>());
  class_<CSmallWeapon, bases<CWeapon>, boost::noncopyable>("CSmallWeapon");
  class_<CPotion, bases<CItem>, boost::noncopyable>("CPotionBase");
  class_<CPotionWrapper, bases<CPotion>, boost::noncopyable,
         boost::shared_ptr<CPotionWrapper>>("CPotion")
      .def("onUse", &CPotion::onUse, &CPotionWrapper::defaultOnUse);
  class_<CTile, bases<CMapObject>, boost::noncopyable>("CTile").def(
      "onStep", &CTile::onStep);
}
