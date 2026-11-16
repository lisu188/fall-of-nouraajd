// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
// Historical reconstruction; original bytes are unavailable. See the recovery
// provenance.
#include "building.h"
#include "creature.h"
#include "event.h"
#include "gamescene.h"
#include "interaction.h"
#include "item.h"
#include "map.h"
#include "monster.h"
#include "player.h"
#include "potion.h"

#include "stats.h"
#include "tile.h"
#include "util.h"
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
    QStringFromPython() { converter::registry::push_back(&convertible, &construct, type_id<QString>()); }
    static void *convertible(PyObject *value) { return PyString_Check(value) || PyUnicode_Check(value) ? value : 0; }
    static void construct(PyObject *value, converter::rvalue_from_python_stage1_data *data) {
        handle<> encoded;
        if (PyUnicode_Check(value)) {
            encoded = handle<>(PyUnicode_AsUTF8String(value));
            value = encoded.get();
        }
        char *bytes = 0;
        Py_ssize_t size = 0;
        if (PyString_AsStringAndSize(value, &bytes, &size) == -1) {
            throw_error_already_set();
        }
        void *storage = reinterpret_cast<converter::rvalue_from_python_storage<QString> *>(data)->storage.bytes;
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

class CInteractionWrapper : public Interaction, public wrapper<CInteractionWrapper> {
  public:
    void performAction(Creature *first, Creature *second) override {
        if (override call = get_override("performAction")) {
            call(boost::ref(first), boost::ref(second));
        } else {
            Interaction::performAction(first, second);
        }
    }
    bool configureEffect(Effect *effect) override {
        if (override call = get_override("configureEffect")) {
            return call(boost::ref(effect));
        }
        return Interaction::configureEffect(effect);
    }
    void defaultPerformAction(Creature *first, Creature *second) { Interaction::performAction(first, second); }
    bool defaultConfigureEffect(Effect *effect) { return Interaction::configureEffect(effect); }
};

template <class Result> struct PythonPotionCall {
    static Result call(override function, Creature *creature) {
        return function(boost::ref(creature)).template as<Result>();
    }
};

template <> struct PythonPotionCall<void> {
    static void call(override function, Creature *creature) { function(boost::ref(creature)); }
};

class CPotionWrapper : public Potion, public wrapper<CPotionWrapper> {
  public:
    // The unchanged original module blob spans the native void-to-bool onUse
    // transition.
    using Result = decltype(std::declval<Potion &>().onUse(static_cast<Creature *>(0)));
    Result onUse(Creature *creature) override {
        if (override function = get_override("onUse")) {
            return PythonPotionCall<Result>::call(function, creature);
        }
        return Potion::onUse(creature);
    }
    Result defaultOnUse(Creature *creature) { return Potion::onUse(creature); }
};

static Player *mapPlayer(Map &value) { return value.getScene()->getPlayer(); }

static void moveObject(MapObject &value, int x, int y, int z) { value.moveTo(x, y, z); }

template <class T> static auto nativeName(const T &value, int) -> decltype(QString::fromStdString(value.name)) {
    return QString::fromStdString(value.name);
}
template <class T> static QString nativeName(const T &value, long) { return value.objectName(); }
template <class T>
static auto nativeName(T &value, QString name, int) -> decltype(value.name = name.toStdString(), void()) {
    value.name = name.toStdString();
}
template <class T> static void nativeName(T &value, QString name, long) { value.setObjectName(name); }
static QString objectName(const MapObject &value) { return nativeName(value, 0); }
static void setObjectName(MapObject &value, QString name) { nativeName(value, name, 0); }

template <class T> static void registerObjectCallbacks(const char *name) {
    class_<CWrapper<T>, bases<T>, boost::noncopyable, boost::shared_ptr<CWrapper<T>>>(name)
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
    class_<Map, boost::noncopyable>("Map", no_init)
        .def("addObjectByName", &Map::addObjectByName)
        .def("removeObjectByName", &Map::removeObjectByName)
        .def("removeObject", &Map::removeObject)
        .def("replaceTile", &Map::replaceTile)
        .def("getPlayer", &mapPlayer, return_internal_reference<>())
        .def("getObjectByName", &Map::getObjectByName, return_internal_reference<>())
        .def("getLocationByName", &Map::getLocationByName);
    class_<MapObject, boost::noncopyable>("MapObject", no_init)
        .add_property("name", &objectName, &setObjectName)
        .def("getMap", &MapObject::getMap, return_internal_reference<>())
        .def("moveTo", &moveObject)
        .def("getCoords", &MapObject::getCoords)
        .def("setCoords", &MapObject::setCoords)
        .def("removeFromGame", &MapObject::removeFromGame) PY_PROPERTY_ACCESSOR(MapObject);
    class_<Stats>("Stats") PY_PROPERTY_ACCESSOR(Stats);
    class_<Damage>("Damage") PY_PROPERTY_ACCESSOR(Damage);
    class_<Creature, bases<MapObject>, boost::noncopyable>("Creature", no_init)
        .def("getDmg", &Creature::getDmg)
        .def("hurt", static_cast<void (Creature::*)(int)>(&Creature::hurt))
        .def("hurt", static_cast<void (Creature::*)(Damage)>(&Creature::hurt))
        .def("getWeapon", &Creature::getWeapon, return_internal_reference<>())
        .def("getArmor", &Creature::getArmor, return_internal_reference<>())
        .def("getStats", &Creature::getStats, return_internal_reference<>())
        .def("getHp", &Creature::getHp)
        .def("getHpMax", &Creature::getHpMax)
        .def("getHpRatio", &Creature::getHpRatio)
        .def("getMana", &Creature::getMana)
        .def("getManaMax", &Creature::getManaMax)
        .def("getManaRatio", &Creature::getManaRatio)
        .def("getLevel", &Creature::getLevel)
        .def("heal", &Creature::heal)
        .def("healProc", &Creature::healProc)
        .def("addMana", &Creature::addMana)
        .def("addManaProc", &Creature::addManaProc)
        .def("takeMana", &Creature::takeMana)
        .def("isAlive", &Creature::isAlive)
        .def("isPlayer", &Creature::isPlayer);
    class_<Player, bases<Creature>, boost::noncopyable>("Player", no_init);
    class_<Monster, bases<Creature>, boost::noncopyable>("Monster", no_init);
    class_<Building, bases<MapObject>, boost::noncopyable>("BuildingBase");
    class_<Event, bases<MapObject>, boost::noncopyable>("EventBase");
    registerObjectCallbacks<Building>("Building");
    registerObjectCallbacks<Event>("Event");
    class_<Interaction, bases<MapObject>, boost::noncopyable>("InteractionBase")
        .def("onAction", &Interaction::onAction);
    class_<CInteractionWrapper, bases<Interaction>, boost::noncopyable, boost::shared_ptr<CInteractionWrapper>>(
        "Interaction")
        .def("performAction", &Interaction::performAction, &CInteractionWrapper::defaultPerformAction)
        .def("configureEffect", &Interaction::configureEffect, &CInteractionWrapper::defaultConfigureEffect);
    class_<Effect, boost::noncopyable>("Effect", no_init)
        .def("getBonus", &Effect::getBonus, return_internal_reference<>())
        .def("setBonus", &Effect::setBonus)
        .def("getCaster", &Effect::getCaster, return_internal_reference<>())
        .def("getVictim", &Effect::getVictim, return_internal_reference<>())
        .def("getTimeLeft", &Effect::getTimeLeft)
        .def("getTimeTotal", &Effect::getTimeTotal);
    class_<Item, bases<MapObject>, boost::noncopyable>("Item");
    class_<Armor, bases<Item>, boost::noncopyable>("Armor");
    class_<Belt, bases<Item>, boost::noncopyable>("Belt");
    class_<Helmet, bases<Item>, boost::noncopyable>("Helmet");
    class_<Boots, bases<Item>, boost::noncopyable>("Boots");
    class_<Gloves, bases<Item>, boost::noncopyable>("Gloves");
    class_<Weapon, bases<Item>, boost::noncopyable>("Weapon").def("getInteraction", &Weapon::getInteraction,
                                                                  return_internal_reference<>());
    class_<SmallWeapon, bases<Weapon>, boost::noncopyable>("SmallWeapon");
    class_<Potion, bases<Item>, boost::noncopyable>("PotionBase");
    class_<CPotionWrapper, bases<Potion>, boost::noncopyable, boost::shared_ptr<CPotionWrapper>>("Potion").def(
        "onUse", &Potion::onUse, &CPotionWrapper::defaultOnUse);
    class_<Tile, bases<MapObject>, boost::noncopyable>("Tile").def("onStep", &Tile::onStep);
}
