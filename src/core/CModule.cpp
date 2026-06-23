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
#include <utility>
#include <algorithm>
#include <cctype>
#include <optional>
#include <stdexcept>

#include "CGlobal.h"
#include "../../vstd/veventloop.h"
#include "../gui/CAnimation.h"
#include "../gui/CGui.h"
#include "../gui/CLayout.h"
#include "../gui/object/CMapGraphicsObject.h"
#include "../gui/object/CMinimapGraphicsObject.h"
#include "../gui/object/CSideBar.h"
#include "../gui/object/CStatsGraphicsObject.h"
#include "../gui/panel/CCreatureView.h"
#include "../gui/panel/CGameCharacterPanel.h"
#include "../gui/panel/CGameDialogPanel.h"
#include "../gui/panel/CGameFightPanel.h"
#include "../gui/panel/CGameInventoryPanel.h"
#include "../gui/panel/CGameQuestPanel.h"
#include "../gui/panel/CGameQuestionPanel.h"
#include "../gui/panel/CGameTextPanel.h"
#include "../gui/panel/CGameTradePanel.h"
#include "../gui/panel/CListView.h"
#include "../handler/CHandler.h"
#include "../handler/CRngHandler.h"
#include "../object/CCreature.h"
#include "../object/CDialog.h"
#include "../object/CEffect.h"
#include "../object/CInteraction.h"
#include "../object/CItem.h"
#include "../object/CMapObject.h"
#include "../object/CMarket.h"
#include "../object/CPlayer.h"
#include "../object/CQuest.h"
#include "../object/CTile.h"
#include "../object/CTrigger.h"
#include "CGame.h"
#include "CGameContext.h"
#include "CList.h"
#include "CMap.h"
#include "CProvider.h"
#include "core/CController.h"
#include "core/CJsonUtil.h"
#include "core/CLoader.h"
#include "core/CModuleInit.h"
#include "core/CPlaytestTrace.h"
#include "core/CPythonOverrides.h"
#include "core/CRuntimeBridge.h"
#include "core/CSceneManager.h"
#include "core/CSlotConfig.h"
#include "core/CTags.h"
#include "core/CTypes.h"
#include "core/CUtil.h"
#include "core/CWrapper.h"
#include <pybind11/stl_bind.h>
#include <pybind11/stl.h>

namespace py = pybind11;

PYBIND11_MAKE_OPAQUE(std::vector<std::string>);

int randint(int i, int j) {
    return vstd::rand(i, j); // TODO: unify and document exclusive inclusive
}

std::string jsonify(std::shared_ptr<CGameObject> x) { return JSONIFY(x); }

std::string jsonify_py(const py::handle &value) {
    if (py::isinstance<CGameObject>(value)) {
        return jsonify(value.cast<std::shared_ptr<CGameObject>>());
    }
    throw py::type_error("jsonify() expects a CGameObject instance");
}

py::tuple read_gui_pixels(CGui &gui) {
    SDL_Renderer *renderer = gui.getRenderer();
    if (renderer == nullptr) {
        throw std::runtime_error("CGui has no SDL renderer");
    }

    int width = 0;
    int height = 0;
    if (SDL_GetRendererOutputSize(renderer, &width, &height) != 0) {
        throw std::runtime_error(std::string("SDL_GetRendererOutputSize failed: ") + SDL_GetError());
    }

    const int pitch = width * 4;
    std::vector<unsigned char> pixels(static_cast<size_t>(pitch) * static_cast<size_t>(height));
    if (SDL_RenderReadPixels(renderer, nullptr, SDL_PIXELFORMAT_RGBA32, pixels.data(), pitch) != 0) {
        throw std::runtime_error(std::string("SDL_RenderReadPixels failed: ") + SDL_GetError());
    }

    return py::make_tuple(py::bytes(reinterpret_cast<const char *>(pixels.data()), pixels.size()), width, height);
}

void logger(std::string s) {
    CRuntimeBridge::log_info(std::move(s)); // TODO: add script name
}

static vstd::logger::sink parse_logger_sink(const std::string &sink_name) {
    std::string normalized;
    normalized.reserve(sink_name.size());
    for (char ch : sink_name) {
        normalized.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
    }
    if (normalized == "stdout") {
        return vstd::logger::sink::stdout_sink;
    }
    if (normalized == "stderr") {
        return vstd::logger::sink::stderr_sink;
    }
    if (normalized == "file") {
        return vstd::logger::sink::file_sink;
    }
    if (normalized == "disabled") {
        return vstd::logger::sink::disabled;
    }
    throw std::invalid_argument("Unknown logger sink: " + sink_name);
}

void set_logger_sink(const std::string &sink_name, const std::string &path) {
    const auto target = parse_logger_sink(sink_name);
    if (target == vstd::logger::sink::file_sink && path.empty()) {
        throw std::invalid_argument("File logger sink requires a path");
    }
    CRuntimeBridge::set_logger_sink(target, path);
}

void set_logger_sink_py(const std::string &sink_name, py::object path = py::none()) {
    std::string file_path;
    if (!path.is_none()) {
        file_path = path.cast<std::string>();
    }
    set_logger_sink(sink_name, file_path);
}

void configure_playtest_trace_py(bool enabled = true, py::object output_path = py::none(),
                                 std::size_t max_records = 1000) {
    std::string target;
    if (!output_path.is_none()) {
        target = output_path.cast<std::string>();
    }
    CPlaytestTrace::configure(enabled, target, max_records);
}

py::list map_get_objects(const std::shared_ptr<CMap> &map) {
    py::list objects;
    for (const auto &object : map->getObjects()) {
        objects.append(object);
    }
    return objects;
}

py::list map_get_objects_at_coords(const std::shared_ptr<CMap> &map, Coords coords) {
    py::list objects;
    for (const auto &object : map->getObjectsAtCoords(coords)) {
        objects.append(object);
    }
    return objects;
}

void map_register_navigation_edge(const std::shared_ptr<CMap> &map, Coords source, Coords target, bool enabled = true,
                                  bool bidirectional = false, int movementCost = 1,
                                  py::object sourceObjectName = py::none()) {
    CNavigationEdge edge;
    edge.source = source;
    edge.target = target;
    edge.enabled = enabled;
    edge.bidirectional = bidirectional;
    edge.movementCost = movementCost;
    if (!sourceObjectName.is_none()) {
        edge.sourceObjectName = sourceObjectName.cast<std::string>();
    }
    map->registerNavigationEdge(std::move(edge));
}

bool map_has_navigation_edge(const std::shared_ptr<CMap> &map, Coords source, Coords target,
                             py::object sourceObjectName = py::none()) {
    source = map->normalizeCoords(source);
    target = map->normalizeCoords(target);
    std::optional<std::string> expectedSourceObjectName;
    if (!sourceObjectName.is_none()) {
        expectedSourceObjectName = sourceObjectName.cast<std::string>();
    }
    return std::ranges::any_of(map->getNavigationEdges(), [&](const CNavigationEdge &edge) {
        return edge.source == source && edge.target == target && edge.sourceObjectName == expectedSourceObjectName;
    });
}

void game_object_setattr(CGameObject &self, const std::string &name, const py::handle &value) {
    if (py::isinstance<py::bool_>(value)) {
        self.setBoolProperty(name, value.cast<bool>());
        return;
    }
    if (py::isinstance<py::int_>(value)) {
        self.setNumericProperty(name, value.cast<int>());
        return;
    }
    if (py::isinstance<py::str>(value)) {
        self.setStringProperty(name, value.cast<std::string>());
        return;
    }
    if (py::isinstance<CGameObject>(value)) {
        self.setObjectProperty(name, value.cast<std::shared_ptr<CGameObject>>());
        return;
    }
    throw py::type_error("Unsupported CGameObject property type");
}

py::object game_object_getattr(CGameObject &self, const std::string &name) {
    if (!self.hasProperty(name)) {
        throw py::attribute_error(name);
    }

    try {
        return py::bool_(self.getBoolProperty(name));
    } catch (const std::exception &) {
    }
    try {
        return py::int_(self.getNumericProperty(name));
    } catch (const std::exception &) {
    }
    try {
        return py::str(self.getStringProperty(name));
    } catch (const std::exception &) {
    }
    try {
        return py::cast(self.getObjectProperty<CGameObject>(name));
    } catch (const std::exception &) {
    }

    throw py::attribute_error(name);
}

py::list graphics_children(CGameGraphicsObject &self) {
    py::list children;
    for (const auto &child : self.getChildren()) {
        children.append(child);
    }
    return children;
}

py::list graphics_proxied_objects(CProxyTargetGraphicsObject &self, const std::shared_ptr<CGui> &gui, int x, int y) {
    py::list objects;
    for (const auto &object : self.getProxiedObjects(gui, x, y)) {
        objects.append(object);
    }
    return objects;
}

py::list list_view_collection_to_py(const CListView::collection_pointer &collection) {
    py::list objects;
    for (const auto &object : *collection) {
        objects.append(object);
    }
    return objects;
}

std::vector<std::shared_ptr<CCreature>> creature_iterable_to_vector(const py::iterable &iterable) {
    std::vector<std::shared_ptr<CCreature>> creatures;
    for (const auto &item : iterable) {
        creatures.push_back(item.is_none() ? nullptr : item.cast<std::shared_ptr<CCreature>>());
    }
    return creatures;
}

std::shared_ptr<CGameObject> cast_registered_python_object(const py::object &instance) {
    if (py::isinstance<CBuilding>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CBuilding>>());
    }
    if (py::isinstance<CEvent>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CEvent>>());
    }
    if (py::isinstance<CInteraction>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CInteraction>>());
    }
    if (py::isinstance<CEffect>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CEffect>>());
    }
    if (py::isinstance<CTile>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CTile>>());
    }
    if (py::isinstance<CPotion>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CPotion>>());
    }
    if (py::isinstance<CScroll>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CScroll>>());
    }
    if (py::isinstance<CTrigger>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CTrigger>>());
    }
    if (py::isinstance<CQuest>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CQuest>>());
    }
    if (py::isinstance<CPlugin>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CPlugin>>());
    }
    if (py::isinstance<CDialog>(instance)) {
        return std::static_pointer_cast<CGameObject>(instance.cast<std::shared_ptr<CDialog>>());
    }
    return instance.cast<std::shared_ptr<CGameObject>>();
}

extern void initModule1();

#define PY_WRAP_GENERIC_DOC(fcn, doc) m.def(#fcn, fcn, doc)

void register_python_binding_type_metadata() {
    CTypes::register_type_metadata<CStats, CGameObject>();
    CTypes::register_type_metadata<CDamage, CGameObject>();

    CTypes::register_type_metadata<CMapObject, CGameObject>();
    CTypes::register_type_metadata<CBuilding, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CBuilding>, CBuilding, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CEvent, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CEvent>, CEvent, CMapObject, CGameObject>();

    CTypes::register_type_metadata<CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CWeapon, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CSmallWeapon, CWeapon, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CArmor, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CHelmet, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CBoots, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CBelt, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CGloves, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CPotion, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CPotion>, CPotion, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CScroll, CItem, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CScroll>, CScroll, CItem, CMapObject, CGameObject>();

    CTypes::register_type_metadata<CEffect, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CEffect>, CEffect, CGameObject>();
    CTypes::register_type_metadata<CInteraction, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CInteraction>, CInteraction, CGameObject>();
    CTypes::register_type_metadata<CTile, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CTile>, CTile, CGameObject>();

    CTypes::register_type_metadata<CMarket, CGameObject>();
    CTypes::register_type_metadata<CDialog, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CDialog>, CDialog, CGameObject>();
    CTypes::register_type_metadata<CDialogOption, CGameObject>();
    CTypes::register_type_metadata<CDialogState, CGameObject>();
    CTypes::register_type_metadata<CTrigger, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CTrigger>, CTrigger, CGameObject>();
    CTypes::register_type_metadata<CQuest, CGameObject>();
    CTypes::register_type_metadata<CWrapper<CQuest>, CQuest, CGameObject>();

    CTypes::register_type_metadata<CFightController, CGameObject>();
    CTypes::register_type_metadata<CPlayerFightController, CFightController, CGameObject>();
    CTypes::register_type_metadata<CMonsterFightController, CFightController, CGameObject>();
    CTypes::register_type_metadata<CController, CGameObject>();
    CTypes::register_type_metadata<CPlayerController, CController, CGameObject>();
    CTypes::register_type_metadata<CTargetController, CController, CGameObject>();
    CTypes::register_type_metadata<CRandomController, CController, CGameObject>();
    CTypes::register_type_metadata<CGroundController, CController, CGameObject>();
    CTypes::register_type_metadata<CRangeController, CController, CGameObject>();
    CTypes::register_type_metadata<CNpcRandomController, CController, CGameObject>();

    CTypes::register_type_metadata<CCreature, CMapObject, CGameObject>();
    CTypes::register_type_metadata<CPlayer, CCreature, CMapObject, CGameObject>();
}

void init_game_module(py::module_ &m) {
    CPlaytestTrace::configureFromEnvironment();
    register_python_binding_type_metadata();

    py::enum_<CTag>(m, "CTag", "Canonical gameplay tag identifier.")
        .value("BUFF", CTag::Buff)
        .value("HEAL", CTag::Heal)
        .value("MANA", CTag::Mana)
        .value("QUEST", CTag::Quest)
        .value("STUN", CTag::Stun)
        .value("WAND", CTag::Wand);

    py::class_<CGameObject, std::shared_ptr<CGameObject>>(
        m, "CGameObject", "Base engine object with dynamic string, numeric, bool, and object properties.")
        .def("getName", &CGameObject::getName, "Return the object name.")
        .def("getType", &CGameObject::getType, "Return the runtime class/type name.")
        .def("getTypeId", &CGameObject::getTypeId, "Return the configured type id used to spawn this object.")
        .def("getGame", &CGameObject::getGame, "Return the owning game instance.")
        .def("getStringProperty", &CGameObject::getStringProperty, "Return a string property by name.")
        .def("getNumericProperty", &CGameObject::getNumericProperty, "Return an integer property by name.")
        .def("getBoolProperty", &CGameObject::getBoolProperty, "Return a boolean property by name.")
        .def("setStringProperty", &CGameObject::setStringProperty, "Set a string property by name.")
        .def("setNumericProperty", &CGameObject::setNumericProperty, "Set an integer property by name.")
        .def("setBoolProperty", &CGameObject::setBoolProperty, "Set a boolean property by name.")
        .def("notifyPropertyChanged", &CGameObject::notifyPropertyChanged,
             "Emit generic and property-specific property change signals.")
        .def("getObjectProperty", &CGameObject::getObjectProperty<CGameObject>, "Return an object property by name.")
        .def("setObjectProperty", &CGameObject::setObjectProperty<CGameObject>, "Set an object property by name.")
        .def("incProperty", &CGameObject::incProperty, "Increment an integer property by value.")
        .def("ptr", &CGameObject::ptr<CGameObject>, "Return this object as a shared pointer.")
        .def("clone", &CGameObject::clone<CGameObject>, "Clone this object using engine serialization.")
        .def("addTag", py::overload_cast<CTag>(&CGameObject::addTag), "Add a canonical tag enum to this object.")
        .def("addTag", py::overload_cast<const std::string &>(&CGameObject::addTag),
             "Add a canonical tag string to this object.")
        .def("removeTag", py::overload_cast<CTag>(&CGameObject::removeTag),
             "Remove a canonical tag enum from this object.")
        .def("removeTag", py::overload_cast<const std::string &>(&CGameObject::removeTag),
             "Remove a canonical tag string from this object.")
        .def("hasTag", py::overload_cast<CTag>(&CGameObject::hasTag),
             "Return whether this object has the given canonical tag enum.")
        .def("hasTag", py::overload_cast<const std::string &>(&CGameObject::hasTag),
             "Return whether this object has the given canonical tag string.")
        .def("__setattr__", &game_object_setattr, "Alias for dynamic property assignment.")
        .def("__getattr__", &game_object_getattr, "Alias for dynamic property lookup.");

    py::class_<Coords>(m, "Coords", "3D integer coordinates (x, y, z).")
        .def(py::init<int, int, int>())
        .def_readonly("x", &Coords::x)
        .def_readonly("y", &Coords::y)
        .def_readonly("z", &Coords::z);

    std::shared_ptr<CGameObject> (CGame::*createObject)(std::string) = &CGame::createObject<CGameObject>;

    py::class_<CScriptHandler, std::shared_ptr<CScriptHandler>>(m, "CScriptHandler",
                                                                "Python script execution service.");

    py::class_<CGameContext, std::shared_ptr<CGameContext>>(m, "CGameContext",
                                                            "Runtime service context owned by a game instance.")
        .def("getObjectHandler", &CGameContext::getObjectHandler, "Return the object factory/registry handler.")
        .def("getGuiHandler", &CGameContext::getGuiHandler, "Return the GUI handler service.")
        .def("getScriptHandler", &CGameContext::getScriptHandler, "Return the Python script execution service.")
        .def("getRngHandler", &CGameContext::getRngHandler, "Return the random encounter/loot handler.")
        .def("isActive", &CGameContext::isActive, "Return whether this game context still accepts session work.")
        .def("shutdown", static_cast<void (CGameContext::*)()>(&CGameContext::shutdown),
             "Explicitly shut down this game context and release session state.")
        .def("getTransitionGeneration", &CGameContext::getTransitionGeneration,
             "Return the current transition/session generation.")
        .def("captureTransitionGeneration", &CGameContext::captureTransitionGeneration,
             "Capture the current transition/session generation for deferred callbacks.")
        .def("isTransitionGenerationCurrent", &CGameContext::isTransitionGenerationCurrent,
             "Return whether a captured transition/session generation is still current.");

    py::enum_<CSceneManager::TransitionState>(m, "CSceneTransitionState", "Scene transition lifecycle state.")
        .value("Idle", CSceneManager::TransitionState::Idle)
        .value("TransitionPending", CSceneManager::TransitionState::TransitionPending)
        .value("Transitioning", CSceneManager::TransitionState::Transitioning);

    bool (CSceneManager::*requestMapChange)(const std::shared_ptr<CGame> &, std::string) =
        &CSceneManager::requestMapChange;

    py::class_<CSceneManager, std::shared_ptr<CSceneManager>>(m, "CSceneManager",
                                                              "Owns queued map transition state and execution.")
        .def("requestMapChange", requestMapChange, "Queue a map transition request.")
        .def("isTransitionPending", &CSceneManager::isTransitionPending,
             "Return whether a map transition is pending or executing.")
        .def("getTransitionState", &CSceneManager::getTransitionState, "Return the current transition state.")
        .def("getTransitionStateName", &CSceneManager::getTransitionStateName,
             "Return the current transition state name.")
        .def("getPendingMapName", &CSceneManager::getPendingMapName, "Return the queued target map name.");

    py::class_<CGame, CGameObject, std::shared_ptr<CGame>>(
        m, "CGame", "Top-level game container holding the active map, handlers, and GUI.")
        .def("getMap", &CGame::getMap, "Return the currently loaded map.")
        .def("changeMap", &CGame::changeMap, "Load and switch to another map.")
        .def("loadPlugin", &CGame::loadPlugin, "Load a plugin object into the game.")
        .def("getContext", &CGame::getContext, "Return the runtime service context.")
        .def("getGuiHandler", &CGame::getGuiHandler, "Return the GUI handler service.")
        .def("getObjectHandler", &CGame::getObjectHandler, "Return the object factory/registry handler.")
        .def("getSceneManager", &CGame::getSceneManager, "Return the scene transition manager.")
        .def("getRngHandler", &CGame::getRngHandler, "Return the random encounter/loot handler.")
        .def("createObject", createObject, "Create an object by configured type id.")
        .def("getGui", &CGame::getGui, "Return the GUI root object.");

    py::class_<CGameGraphicsObject, CGameObject, std::shared_ptr<CGameGraphicsObject>>(
        m, "CGameGraphicsObject", "Base class for GUI graphics objects.")
        .def("getGui", &CGameGraphicsObject::getGui, "Return the owning GUI object.")
        .def("getParent", &CGameGraphicsObject::getParent, "Return the parent graphics object.")
        .def("getChildren", &graphics_children, "Return this graphics object's children.")
        .def("addChild", &CGameGraphicsObject::addChild, "Attach a graphics child.")
        .def("pushChild", &CGameGraphicsObject::pushChild, "Attach a graphics child above existing children.")
        .def("removeChild", &CGameGraphicsObject::removeChild, "Detach a graphics child.")
        .def("findChild", py::overload_cast<const std::string &>(&CGameGraphicsObject::findChild),
             "Find a child by C++ type name.")
        .def(
            "keyboardEvent",
            [](CGameGraphicsObject &self, const std::shared_ptr<CGui> &gui, int type, int key) {
                return self.keyboardEvent(gui, static_cast<SDL_EventType>(type), key);
            },
            "Dispatch a keyboard event to this object.")
        .def(
            "mouseEvent",
            [](CGameGraphicsObject &self, const std::shared_ptr<CGui> &gui, int type, int button, int x, int y) {
                return self.mouseEvent(gui, static_cast<SDL_EventType>(type), button, x, y);
            },
            "Dispatch a mouse button event to this object.")
        .def(
            "getResolvedRect",
            [](CGameGraphicsObject &self) {
                auto layout = self.getLayout();
                if (!layout) {
                    return py::make_tuple(0, 0, 0, 0);
                }
                auto rect = layout->getRect(self.ptr<CGameGraphicsObject>());
                if (!rect) {
                    return py::make_tuple(0, 0, 0, 0);
                }
                return py::make_tuple(rect->x, rect->y, rect->w, rect->h);
            },
            "Return resolved runtime layout as (x, y, width, height).");

    py::class_<CGui, CGameGraphicsObject, std::shared_ptr<CGui>>(m, "CGui", "Game GUI root object.")
        .def("getGame", &CGui::getGame, "Return the owning game.")
        .def("hasDragSession", &CGui::hasDragSession, "Return whether a GUI drag transaction is active.")
        .def("hasPointerCapture", &CGui::hasPointerCapture, "Return whether a GUI widget owns pointer capture.")
        .def("read_pixels", &read_gui_pixels, "Read the current SDL renderer pixels as RGBA bytes, width, and height.");

    py::class_<CAnimation, CGameGraphicsObject, std::shared_ptr<CAnimation>>(m, "CAnimation",
                                                                             "Base animation graphics object.")
        .def("getObject", &CAnimation::getObject, "Return object represented by this animation.")
        .def("setObject", &CAnimation::setObject, "Set object represented by this animation.");
    py::class_<CStaticAnimation, CAnimation, std::shared_ptr<CStaticAnimation>>(m, "CStaticAnimation",
                                                                                "Static bitmap animation.")
        .def("getRotation", &CStaticAnimation::getRotation, "Return configured rotation.")
        .def("setRotation", &CStaticAnimation::setRotation, "Set render rotation.")
        .def("setColorMod", &CStaticAnimation::setColorMod, "Set texture color modulation.")
        .def("clearColorMod", &CStaticAnimation::clearColorMod, "Clear texture color modulation.")
        .def(
            "renderObject",
            [](CStaticAnimation &self, const std::shared_ptr<CGui> &gui, int x, int y, int w, int h, int frame_time) {
                self.renderObject(gui, CUtil::rect(x, y, w, h), frame_time);
            },
            "Render the static animation into a rectangle.");
    py::class_<CDynamicAnimation, CAnimation, std::shared_ptr<CDynamicAnimation>>(m, "CDynamicAnimation",
                                                                                  "Frame-table animation.")
        .def("initialize", &CDynamicAnimation::initialize, "Load animation frames from configuration.")
        .def(
            "renderObject",
            [](CDynamicAnimation &self, const std::shared_ptr<CGui> &gui, int x, int y, int w, int h, int frame_time) {
                self.renderObject(gui, CUtil::rect(x, y, w, h), frame_time);
            },
            "Render the dynamic animation into a rectangle.");
    py::class_<CSelectionBox, CAnimation, std::shared_ptr<CSelectionBox>>(m, "CSelectionBox",
                                                                          "Selection outline graphics object.")
        .def("getThickness", &CSelectionBox::getThickness, "Return outline thickness.")
        .def("setThickness", &CSelectionBox::setThickness, "Set outline thickness.")
        .def(
            "renderObject",
            [](CSelectionBox &self, const std::shared_ptr<CGui> &gui, int x, int y, int w, int h, int frame_time) {
                self.renderObject(gui, CUtil::rect(x, y, w, h), frame_time);
            },
            "Render the selection outline into a rectangle.");

    py::class_<CStatsGraphicsObject, CGameGraphicsObject, std::shared_ptr<CStatsGraphicsObject>>(
        m, "CStatsGraphicsObject");

    py::class_<CSideBar, CGameGraphicsObject, std::shared_ptr<CSideBar>>(m, "CSideBar");

    py::class_<CMinimapGraphicsObject, CGameGraphicsObject, std::shared_ptr<CMinimapGraphicsObject>>(
        m, "CMinimapGraphicsObject", "Display-only current-level minimap graphics object.");

    py::class_<CProxyTargetGraphicsObject, CGameGraphicsObject, std::shared_ptr<CProxyTargetGraphicsObject>>(
        m, "CProxyTargetGraphicsObject", "Graphics object that proxies child graphics for cells.")
        .def("refresh", &CProxyTargetGraphicsObject::refresh, "Refresh proxy cell layout.")
        .def("refreshAll", &CProxyTargetGraphicsObject::refreshAll, "Refresh all proxy cells.")
        .def("refreshObject", &CProxyTargetGraphicsObject::refreshObject, "Refresh one proxy cell.")
        .def("getProxiedObjects", &graphics_proxied_objects, "Return graphics objects proxied for a cell.");

    py::class_<CMapGraphicsObject, CProxyTargetGraphicsObject, std::shared_ptr<CMapGraphicsObject>>(
        m, "CMapGraphicsObject", "Map viewport graphics object.")
        .def("refreshObject", py::overload_cast<Coords>(&CMapGraphicsObject::refreshObject),
             "Refresh map proxies for a map coordinate.");

    py::class_<CCreatureView, CGameGraphicsObject, std::shared_ptr<CCreatureView>>(
        m, "CCreatureView", "Panel widget that renders a creature.")
        .def("getCreature", &CCreatureView::getCreature, "Return the creature shown in this view.");

    bool (CMap::*canStep)(Coords) = &CMap::canStep;
    int (CMap::*getMovementCost)(Coords) = &CMap::getMovementCost;
    std::shared_ptr<CTile> (CMap::*getTile)(int, int, int) = &CMap::getTile;
    void (CMap::*addObject)(const std::shared_ptr<CMapObject> &) = &CMap::addObject;
    void (CMap::*attachPlayerAtEntry)(std::shared_ptr<CPlayer>) = &CMap::attachPlayer;
    void (CMap::*attachPlayerAtCoords)(std::shared_ptr<CPlayer>, Coords) = &CMap::attachPlayer;
    std::vector<Coords> (CMap::*getNavigationNeighbors)(Coords, bool) const = &CMap::getNavigationNeighbors;

    py::class_<CMap, CGameObject, std::shared_ptr<CMap>>(
        m, "CMap", "Runtime map containing tiles, map objects, triggers, and turn state.")
        .def("addObjectByName", &CMap::addObjectByName, "Create and add an object by type id at coordinates.")
        .def("removeObjectByName", &CMap::removeObjectByName, "Remove an object by its name.")
        .def("removeObject", &CMap::removeObject, "Remove a map object instance.")
        .def("replaceTile", &CMap::replaceTile, "Replace a tile at coordinates with a tile type id.")
        .def("getPlayer", &CMap::getPlayer, "Return the player object assigned to this map.")
        .def("detachPlayer", &CMap::detachPlayer, "Detach and return the active player without destroy events.")
        .def("attachPlayer", attachPlayerAtEntry,
             "Attach a player at the map entry and run destination movement hooks.")
        .def("attachPlayer", attachPlayerAtCoords, "Attach a player at coordinates and run destination movement hooks.")
        .def("getLocationByName", &CMap::getLocationByName, "Return Coords for a named location object.")
        .def("removeAll", &CMap::removeObjects, "Remove objects matching a predicate.")
        .def("getEventHandler", &CMap::getEventHandler, "Return the map event handler.")
        .def("addObject", addObject, "Add an existing map object to this map.")
        .def("getGame", &CMap::getGame, "Return the owning game instance.")
        .def("move", &CMap::move, "Advance map simulation by one turn.")
        .def("getObjectByName", &CMap::getObjectByName, "Return a map object by name or None.")
        .def("forObjects", &CMap::forObjects, "Apply a callback for objects matching an optional predicate.")
        .def("canStep", canStep, "Return whether coordinates are walkable.")
        .def("getMovementCost", getMovementCost, "Return the pathfinding movement cost at coordinates.")
        .def("getTile", getTile, "Return the tile at coordinates, creating the layer default when missing.")
        .def("dumpPaths", &CMap::dumpPaths, "Write pathfinding diagnostics to a file path.")
        .def("getNavigationRevision", &CMap::getNavigationRevision,
             "Return the revision counter for registered navigation edges.")
        .def("getEntryX", &CMap::getEntryX, "Return map entry X coordinate.")
        .def("getEntryY", &CMap::getEntryY, "Return map entry Y coordinate.")
        .def("getEntryZ", &CMap::getEntryZ, "Return map entry Z coordinate.")
        .def("getObjects", &map_get_objects, "Return a Python list of map objects.")
        .def("getObjectsAtCoords", &map_get_objects_at_coords,
             "Return a Python list of map objects at the given coordinates.")
        .def("getNavigationNeighbors", getNavigationNeighbors, py::arg("coords"), py::arg("includeSelf") = false,
             "Return cardinal neighbors plus enabled registered navigation edges.")
        .def("registerNavigationEdge", &map_register_navigation_edge, py::arg("source"), py::arg("target"),
             py::arg("enabled") = true, py::arg("bidirectional") = false, py::arg("movementCost") = 1,
             py::arg("sourceObjectName") = py::none(), "Register a navigation edge for map pathing.")
        .def("hasNavigationEdge", &map_has_navigation_edge, py::arg("source"), py::arg("target"),
             py::arg("sourceObjectName") = py::none(), "Return whether a matching navigation edge exists.")
        .def("unregisterNavigationEdgesForObject", &CMap::unregisterNavigationEdgesForObject,
             py::arg("sourceObjectName"), "Remove all navigation edges registered by an object name.")
        .def("getTurn", &CMap::getTurn, "Return the current turn counter.");

    std::shared_ptr<CGameObject> (*createObjectByType)(std::shared_ptr<CObjectHandler>, std::shared_ptr<CGame>,
                                                       std::string) =
        [](std::shared_ptr<CObjectHandler> handler, std::shared_ptr<CGame> game, std::string type) {
            return handler->createObject<CGameObject>(game, type);
        };
    py::class_<CObjectHandler, CGameObject, std::shared_ptr<CObjectHandler>>(
        m, "CObjectHandler", "Factory and type/config registry for runtime objects.")
        .def(
            "registerType",
            [](CObjectHandler &self, std::string name, py::object constructor) {
                self.registerType(std::move(name), [constructor]() {
                    py::gil_scoped_acquire gil;
                    py::object instance = constructor();
                    auto object = cast_registered_python_object(instance);
                    CPythonOverrides::retain(object, instance);
                    return object;
                });
            },
            "Register a class constructor under a class name.")
        .def("createObject", createObjectByType, "Create an object by configured type id.")
        .def(
            "registerConfigJson",
            [](CObjectHandler &self, const std::string &name, const std::string &config) {
                auto parsed = CJsonUtil::from_string(config, "registerConfigJson:" + name);
                if (!parsed) {
                    throw std::runtime_error("Failed to parse object config json for " + name);
                }
                self.registerConfig(name, parsed);
            },
            "Register object configuration from a JSON string.")
        .def("getAllTypes", &CObjectHandler::getAllTypes,
             "Return all registered class names and configured object type ids.")
        .def("getAllSubTypes", &CObjectHandler::getAllSubTypes,
             "Return configured type ids whose class inherits the given base class.");

    py::class_<CGuiHandler, CGameObject, std::shared_ptr<CGuiHandler>>(m, "CGuiHandler",
                                                                       "High-level helper for opening UI panels.")
        .def("showMessage", &CGuiHandler::showMessage, "Show a message panel.")
        .def("showTrade", &CGuiHandler::showTrade, "Open a trade panel.")
        .def("showDialog", &CGuiHandler::showDialog, "Open a dialog panel.")
        .def("showQuestion", &CGuiHandler::showQuestion, "Open a question/choice panel.")
        .def("showSelection", &CGuiHandler::showSelection, "Open a selection panel.")
        .def("showInfo", &CGuiHandler::showInfo, py::arg("message"), py::arg("centered") = false, "Open an info panel.")
        .def("openPanel", &CGuiHandler::openPanel, "Open a configured panel without blocking for user input.")
        .def("showLoot", &CGuiHandler::showLoot, "Show loot acquisition UI.")
        .def("showTooltip", &CGuiHandler::showTooltip, "Show a tooltip panel at screen coordinates.")
        .def("flipPanel", &CGuiHandler::flipPanel, "Toggle a configured panel and bind its hotkey while open.");

    py::class_<CController, CGameObject, std::shared_ptr<CController>>(m, "CController", "Base movement controller.");
    py::class_<CPlayerController, CController, std::shared_ptr<CPlayerController>>(
        m, "CPlayerController", "Controller that follows a queued player path.")
        .def("setTarget", &CPlayerController::setTarget, "Set a pathfinding destination for the player.")
        .def("isCompleted", &CPlayerController::isCompleted,
             "Return whether the queued path has finished or become invalid.");
    py::class_<CTargetController, CController, std::shared_ptr<CTargetController>>(
        m, "CTargetController", "Controller that follows a named map target.")
        .def("getTarget", &CTargetController::getTarget, "Return current target object name.")
        .def("setTarget", &CTargetController::setTarget, "Set target object name.");
    py::class_<CGroundController, CController, std::shared_ptr<CGroundController>>(
        m, "CGroundController", "Controller constrained to a tile type.")
        .def("getTileType", &CGroundController::getTileType, "Return allowed tile type.")
        .def("setTileType", &CGroundController::setTileType, "Set allowed tile type.");
    py::class_<CRangeController, CController, std::shared_ptr<CRangeController>>(
        m, "CRangeController", "Controller that keeps range from a target.")
        .def("getTarget", &CRangeController::getTarget, "Return target object name.")
        .def("setTarget", &CRangeController::setTarget, "Set target object name.")
        .def("getDistance", &CRangeController::getDistance, "Return desired distance from target.")
        .def("setDistance", &CRangeController::setDistance, "Set desired distance from target.");
    py::class_<CFightController, CGameObject, std::shared_ptr<CFightController>>(m, "CFightController",
                                                                                 "Base fight controller.")
        .def("control", &CFightController::control, "Execute one fight-controller turn.");

    void (CRngHandler::*addRandomLoot)(const std::shared_ptr<CCreature> &, int) = &CRngHandler::addRandomLoot;
    py::class_<CRngHandler, CGameObject, std::shared_ptr<CRngHandler>>(m, "CRngHandler",
                                                                       "Random loot and encounter generator.")
        .def("addRandomLoot", addRandomLoot, "Generate random loot for a creature and apply/show it.")
        .def("addRandomEncounter", &CRngHandler::addRandomEncounter,
             "Generate and place random enemy creatures on a map.");

    void (CMapObject::*moveTo)(int, int, int) = &CMapObject::moveTo;
    void (CMapObject::*move)(int, int, int) = &CMapObject::move;
    py::class_<CMapObject, CGameObject, std::shared_ptr<CMapObject>>(m, "CMapObject",
                                                                     "Base object that exists at map coordinates.")
        .def("getMap", &CMapObject::getMap, "Return the map containing this object.")
        .def("moveTo", moveTo, "Move this object to absolute coordinates.")
        .def("move", move, "Move this object by relative coordinate delta.")
        .def("relocateWithoutMoveHooks", &CMapObject::relocateWithoutMoveHooks,
             "Relocate this object without invoking movement hooks.")
        .def("getCoords", &CMapObject::getCoords, "Return current map coordinates.")
        .def("setCoords", &CMapObject::setCoords, "Set map coordinates.");

    auto cbuilding = py::class_<CBuilding, CWrapper<CBuilding>, std::shared_ptr<CBuilding>, CMapObject>(
        m, "CBuilding", "Base building object class.");
    cbuilding.def(py::init_alias<>())
        .def("onCreate", &CBuilding::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CBuilding::onTurn, "Handle onTurn game event.")
        .def("onDestroy", &CBuilding::onDestroy, "Handle onDestroy game event.")
        .def("onLeave", &CBuilding::onLeave, "Handle onLeave game event.")
        .def("onEnter", &CBuilding::onEnter, "Handle onEnter game event.");
    m.attr("CBuildingBase") = cbuilding;

    auto cevent = py::class_<CEvent, CWrapper<CEvent>, std::shared_ptr<CEvent>, CMapObject>(
        m, "CEvent", "Base map event object class.");
    cevent.def(py::init_alias<>())
        .def("onCreate", &CEvent::onCreate, "Handle onCreate game event.")
        .def("onTurn", &CEvent::onTurn, "Handle onTurn game event.")
        .def("onLeave", &CEvent::onLeave, "Handle onLeave game event.")
        .def("onDestroy", &CEvent::onDestroy, "Handle onDestroy game event.")
        .def("onEnter", &CEvent::onEnter, "Handle onEnter game event.");
    m.attr("CEventBase") = cevent;

    auto cinteraction =
        py::class_<CInteraction, CWrapper<CInteraction>, std::shared_ptr<CInteraction>, CGameObject>(
            m, "CInteraction", "Base interaction/action definition.")
            .def(py::init_alias<>())
            .def("onAction", &CInteraction::onAction, "Engine callback when the interaction is activated.");
    cinteraction
        .def("performAction", &CInteraction::performAction,
             "Perform the interaction between source and target creatures.")
        .def("configureEffect", &CInteraction::configureEffect, "Configure an effect instance before it is applied.");
    m.attr("CInteractionBase") = cinteraction;

    py::class_<CDamage, CGameObject, std::shared_ptr<CDamage>>(m, "CDamage",
                                                               "CDamage packet with typed damage components.");
    py::class_<CStats, CGameObject, std::shared_ptr<CStats>>(m, "CStats",
                                                             "Creature stat container used for combat calculations.")
        .def("setStrength", &CStats::setStrength, "Set strength.")
        .def("setAgility", &CStats::setAgility, "Set agility.")
        .def("setStamina", &CStats::setStamina, "Set stamina.")
        .def("setIntelligence", &CStats::setIntelligence, "Set intelligence.")
        .def("setArmor", &CStats::setArmor, "Set armor reduction percentage.")
        .def("setBlock", &CStats::setBlock, "Set block chance percentage.")
        .def("setDmgMin", &CStats::setDmgMin, "Set minimum base damage.")
        .def("setDmgMax", &CStats::setDmgMax, "Set maximum base damage.")
        .def("setHit", &CStats::setHit, "Set hit chance modifier.")
        .def("setCrit", &CStats::setCrit, "Set critical chance percentage.")
        .def("getMainValue", &CStats::getMainValue, "Return current value of the configured main stat.")
        .def("addBonus", &CStats::addBonus, "Add all numeric stats from another CStats object.")
        .def("removeBonus", &CStats::removeBonus, "Remove all numeric stats from another CStats object.")
        .def("getText", &CStats::getText, "Return formatted stat summary text.");

    auto ctile =
        py::class_<CTile, CWrapper<CTile>, std::shared_ptr<CTile>, CGameObject>(m, "CTile", "Base tile class.");
    ctile.def(py::init_alias<>())
        .def("onStep", &CTile::onStep, "Handle a creature stepping on this tile.")
        .def("getMovementCost", &CTile::getMovementCost, "Return this tile's pathfinding movement cost.")
        .def("setMovementCost", &CTile::setMovementCost, "Set this tile's pathfinding movement cost.")
        .def("getTileType", &CTile::getTileType, "Return this tile's terrain type.");
    m.attr("CTileBase") = ctile;

    py::class_<CItem, CMapObject, std::shared_ptr<CItem>>(m, "CItem", "Base inventory/equipment item.");
    auto cpotion = py::class_<CPotion, CWrapper<CPotion>, std::shared_ptr<CPotion>, CItem>(m, "CPotion",
                                                                                           "Base potion item class.");
    cpotion.def(py::init_alias<>()).def("onUse", &CPotion::onUse, "Handle potion use event.");
    m.attr("CPotionBase") = cpotion;
    auto cscroll = py::class_<CScroll, CWrapper<CScroll>, std::shared_ptr<CScroll>, CItem>(m, "CScroll",
                                                                                           "Base scroll item class.");
    cscroll.def(py::init_alias<>())
        .def("onUse", &CScroll::onUse, "Handle scroll use event.")
        .def("isDisposable", &CScroll::isDisposable, "Return whether the scroll is consumed on use.");
    m.attr("CScrollBase") = cscroll;

    py::class_<CGameEvent, CGameObject, std::shared_ptr<CGameEvent>>(m, "CGameEvent", "Base event object.");
    py::class_<CGameEventCaused, CGameEvent, std::shared_ptr<CGameEventCaused>>(m, "CGameEventCaused",
                                                                                "Event carrying a causing game object.")
        .def("getCause", &CGameEventCaused::getCause, "Return the object that caused this event.");

    auto ctrigger = py::class_<CTrigger, CWrapper<CTrigger>, std::shared_ptr<CTrigger>, CGameObject>(
        m, "CTrigger", "Base trigger class.");
    ctrigger.def(py::init_alias<>())
        .def("trigger", &CTrigger::trigger, "Handle trigger execution for an object and event.");
    m.attr("CTriggerBase") = ctrigger;

    auto cquest =
        py::class_<CQuest, CWrapper<CQuest>, std::shared_ptr<CQuest>, CGameObject>(m, "CQuest", "Base quest class.");
    cquest.def(py::init_alias<>())
        .def("isCompleted", &CQuest::isCompleted, "Return whether quest objectives are completed.")
        .def("onComplete", &CQuest::onComplete, "Handle quest completion callback.")
        .def("getObjective", &CQuest::getObjective, "Return current quest objective text.")
        .def("getReward", &CQuest::getReward, "Return quest reward text.")
        .def("getHint", &CQuest::getHint, "Return optional quest hint text.");
    m.attr("CQuestBase") = cquest;

    auto cdialog = py::class_<CDialog, CWrapper<CDialog>, std::shared_ptr<CDialog>, CGameObject>(
        m, "CDialog", "Base dialog definition.");
    cdialog.def(py::init_alias<>())
        .def("invokeAction", &CDialog::invokeAction, "Run a named dialog action callback.")
        .def("invokeCondition", &CDialog::invokeCondition, "Evaluate a named dialog condition callback.")
        .def("getStates", &CDialog::getStates, "Return dialog states.")
        .def("setStates", &CDialog::setStates, "Replace dialog states.");
    m.attr("CDialogBase") = cdialog;
    m.attr("CDialogBase2") = cdialog;

    py::class_<CDialogOption, CGameObject, std::shared_ptr<CDialogOption>>(m, "CDialogOption",
                                                                           "Single selectable dialog option.");
    py::class_<CDialogState, CGameObject, std::shared_ptr<CDialogState>>(m, "CDialogState", "Dialog state node.")
        .def("getOptions", &CDialogState::getOptions, "Return dialog options.")
        .def("setOptions", &CDialogState::setOptions, "Replace dialog options.");

    py::class_<CEventHandler, CGameObject, std::shared_ptr<CEventHandler>>(m, "CEventHandler",
                                                                           "Dispatcher for game/map events.")
        .def("registerTrigger", &CEventHandler::registerTrigger, "Register a trigger for an event type.");

    py::enum_<CFightOutcome>(m, "CFightOutcome")
        .value("invalid", CFightOutcome::invalid)
        .value("attackerVictory", CFightOutcome::attackerVictory)
        .value("attackerDefeat", CFightOutcome::attackerDefeat)
        .value("stalemate", CFightOutcome::stalemate)
        .value("interrupted", CFightOutcome::interrupted);

    py::class_<CFightHandler, std::shared_ptr<CFightHandler>>(m, "CFightHandler", "Combat resolution service.")
        .def("fight", &CFightHandler::fight, "Run a fight between two creatures.")
        .def_static("applyEffects", &CFightHandler::applyEffects, "Apply active effects to a creature.")
        .def(
            "fightMany",
            [](std::shared_ptr<CCreature> attacker, const py::iterable &opponents) {
                std::vector<std::shared_ptr<CCreature>> encounter;
                for (const auto &opponent : opponents) {
                    encounter.push_back(opponent.cast<std::shared_ptr<CCreature>>());
                }
                return CFightHandler::fightMany(attacker, encounter);
            },
            "Run a fight between one creature and multiple opponents.")
        .def_static(
            "fightManyOutcome",
            [](std::shared_ptr<CCreature> attacker, const py::iterable &opponents) {
                return CFightHandler::fightManyOutcome(attacker, creature_iterable_to_vector(opponents));
            },
            "Run a multi-opponent fight and return the detailed C++ outcome.");

    py::class_<CSlot, CGameObject, std::shared_ptr<CSlot>>(m, "CSlot", "Equipment slot configuration entry.")
        .def("getSlotName", &CSlot::getSlotName, "Return slot id.")
        .def("setSlotName", &CSlot::setSlotName, "Set slot id.")
        .def("getTypes", &CSlot::getTypes, "Return class names that can fit this slot.")
        .def("setTypes", &CSlot::setTypes, "Set class names that can fit this slot.");

    py::class_<CSlotConfig, CGameObject, std::shared_ptr<CSlotConfig>>(m, "CSlotConfig",
                                                                       "Equipment slot compatibility table.")
        .def("getConfiguration", &CSlotConfig::getConfiguration, "Return configured slots.")
        .def("setConfiguration", &CSlotConfig::setConfiguration, "Replace configured slots.")
        .def("canFit", &CSlotConfig::canFit, "Return whether an item can be equipped in a slot.")
        .def("getFittingSlots", &CSlotConfig::getFittingSlots, "Return all slots that accept an item.");

    py::class_<CMarket, CGameObject, std::shared_ptr<CMarket>>(m, "CMarket", "Trading inventory and prices.")
        .def("add", &CMarket::add, "Add an item to the market.")
        .def("remove", &CMarket::remove, "Remove an item from the market.")
        .def("getItems", &CMarket::getItems, "Return market inventory.")
        .def("setItems", &CMarket::setItems, "Replace market inventory.")
        .def("sellItem", &CMarket::sellItem, "Sell an item from the market to a creature.")
        .def("buyItem", &CMarket::buyItem, "Buy an owned item from a creature.")
        .def("getSellCost", &CMarket::getSellCost, "Return customer purchase price for an item.")
        .def("getBuyCost", &CMarket::getBuyCost, "Return merchant buyback price for an item.");

    py::class_<CTooltipHandler, CGameObject, std::shared_ptr<CTooltipHandler>>(m, "CTooltipHandler",
                                                                               "Tooltip text builder.")
        .def_static("buildTooltip", &CTooltipHandler::buildTooltip, "Build tooltip text for an object.");

    py::class_<CGameLoader, std::shared_ptr<CGameLoader>>(m, "CGameLoader",
                                                          "Factory helpers for loading game sessions and maps.")
        .def("loadGame", &CGameLoader::loadGame, "Create and initialize a game instance.")
        .def("startGameWithPlayer", &CGameLoader::startGameWithPlayer, "Start a map with a specific player template.")
        .def("startRandomGameWithPlayer", &CGameLoader::startRandomGameWithPlayer,
             "Start a random map with a specific player template.")
        .def("startGame", &CGameLoader::startGame, "Start a specific map with current player data.")
        .def("loadGui", &CGameLoader::loadGui, "Load and attach GUI objects for a game.")
        .def("loadSavedGame", &CGameLoader::loadSavedGame, "Load a saved game state from storage.");

    py::class_<CMapLoader, std::shared_ptr<CMapLoader>>(m, "CMapLoader", "Helpers for loading map resources.")
        .def("loadNewMapWithPlayer", &CMapLoader::loadNewMapWithPlayer, "Load a map and place a player template.")
        .def("loadNewMap", &CMapLoader::loadNewMap, "Load a map without changing the active player.")
        .def("save", &CMapLoader::save, "Save the current map state to a named save slot.");

    py::class_<CPluginLoader, std::shared_ptr<CPluginLoader>>(m, "CPluginLoader", "Helpers for loading plugins.")
        .def("loadPlugin", &CPluginLoader::loadPlugin, "Load a Python plugin resource into the game.")
        .def("loadCppPlugin", &CPluginLoader::loadCppPlugin, "Load a compiled C++ plugin type into the game.")
        .def_static("loadDynamicPlugin", &CPluginLoader::loadDynamicPlugin, py::arg("game"), py::arg("library"),
                    py::arg("entry") = "game_plugin_load_v1", "Load a dynamic C++ plugin shared library into the game.")
        .def("loadGlobalPlugins", &CPluginLoader::loadGlobalPlugins, "Load configured global plugins.")
        .def("loadMapPlugins", &CPluginLoader::loadMapPlugins, "Load configured plugins for a map.");

    auto cplugin = py::class_<CPlugin, CWrapper<CPlugin>, std::shared_ptr<CPlugin>, CGameObject>(m, "CPlugin",
                                                                                                 "Base plugin class.");
    cplugin.def(py::init_alias<>()).def("load", &CPlugin::load, "Load plugin content into a game.");
    m.attr("CPluginBase") = cplugin;

    py::class_<vstd::event_loop<>, std::shared_ptr<vstd::event_loop<>>>(m, "event_loop",
                                                                        "Global async event loop utility.")
        .def_static("instance", &CRuntimeBridge::event_loop_instance, "Return the singleton event loop instance.")
        .def("run", &vstd::event_loop<>::run, "Process queued tasks/events once.")
        .def("invoke", &vstd::event_loop<>::invoke, "Queue a callable for later execution.");

    auto vector_string = py::bind_vector<std::vector<std::string>>(m, "std::vector<std::string>");
    vector_string.doc() = "Mutable list of strings.";

    py::class_<CResourcesProvider, std::shared_ptr<CResourcesProvider>>(m, "CResourcesProvider",
                                                                        "Access to packaged resource files.")
        .def("getInstance", &CResourcesProvider::getInstance, "Return singleton resource provider.")
        .def("getPath", &CResourcesProvider::getPath, "Resolve a resource path relative to the active resource root.")
        .def("load", &CResourcesProvider::load, "Load a resource file as text.")
        .def("getFiles", &CResourcesProvider::getFiles, "List files under a resource path.");

    auto ceffect = py::class_<CEffect, CWrapper<CEffect>, std::shared_ptr<CEffect>, CGameObject>(
                       m, "CEffect", "Base status effect class.")
                       .def(py::init_alias<>())
                       .def("apply", &CEffect::apply, "Apply one effect tick to the given creature.")
                       .def("getBonus", &CEffect::getBonus, "Return effect stat bonus object.")
                       .def("setBonus", &CEffect::setBonus, "Set effect stat bonus object.")
                       .def("getCaster", &CEffect::getCaster, "Return creature that applied the effect.")
                       .def("getVictim", &CEffect::getVictim, "Return creature affected by the effect.")
                       .def("getTimeLeft", &CEffect::getTimeLeft, "Return remaining effect duration in turns.")
                       .def("onEffect", &CEffect::onEffect, "Apply effect behavior for one tick.");
    m.attr("CEffectBase") = ceffect;

    py::class_<CWeapon, CItem, std::shared_ptr<CWeapon>>(m, "CWeapon", "Weapon item.")
        .def("getInteraction", &CWeapon::getInteraction, "Return interaction used when this weapon is applied.");

    void (CCreature::*hurtInt)(int) = &CCreature::hurt;
    void (CCreature::*hurtFloat)(float) = &CCreature::hurt;
    void (CCreature::*hurtDmg)(std::shared_ptr<CDamage>) = &CCreature::hurt;
    void (CCreature::*addItemByName)(std::string) = &CCreature::addItem;
    void (CCreature::*addItemByObject)(std::shared_ptr<CItem>) = &CCreature::addItem;
    bool (CCreature::*hasItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::hasItem;
    void (CCreature::*removeItem)(std::function<bool(std::shared_ptr<CItem>)>, bool) = &CCreature::removeItem;
    void (CCreature::*removeQuestItem)(std::function<bool(std::shared_ptr<CItem>)>) = &CCreature::removeQuestItem;
    py::class_<CCreature, CMapObject, std::shared_ptr<CCreature>>(
        m, "CCreature", "Creature that can move, fight, and manage inventory.")
        .def("getDmg", &CCreature::getDmg, "Roll outgoing attack damage.")
        .def("hurt", hurtInt, "Apply raw damage value (int).")
        .def("hurt", hurtDmg, "Apply structured CDamage object.")
        .def("hurt", hurtFloat, "Apply damage value (float), rounded to int.")
        .def("getWeapon", &CCreature::getWeapon, "Return equipped weapon or None.")
        .def(
            "unequipArmor", [](CCreature &creature) { creature.setArmor(nullptr); }, "Unequip current armor item.")
        .def("getHpRatio", &CCreature::getHpRatio, "Return HP percentage (0-100).")
        .def("isAlive", &CCreature::isAlive, "Return whether HP is above zero.")
        .def("getMana", &CCreature::getMana, "Return current mana.")
        .def("healProc", &CCreature::healProc, "Restore HP by percentage of max HP.")
        .def("heal", &CCreature::heal, "Restore HP by fixed amount (0 means full heal).")
        .def("getHpMax", &CCreature::getHpMax, "Return maximum HP.")
        .def("getLevel", &CCreature::getLevel, "Return level.")
        .def("getStats", &CCreature::getStats, "Return aggregated combat stats.")
        .def("addManaProc", &CCreature::addManaProc, "Restore mana by percentage of max mana.")
        .def("isPlayer", &CCreature::isPlayer, "Return whether this creature is the active player.")
        .def("isNpc", &CCreature::isNpc, "Return whether this creature is marked as NPC.")
        .def("getController", &CCreature::getController, "Return the movement controller.")
        .def("setController", &CCreature::setController, "Set the movement controller.")
        .def("getFightController", &CCreature::getFightController, "Return the fight controller.")
        .def("setFightController", &CCreature::setFightController, "Set the fight controller.")
        .def("getHp", &CCreature::getHp, "Return current HP.")
        .def("setHp", &CCreature::setHp, "Set current HP.")
        .def("setMana", &CCreature::setMana, "Set current mana.")
        .def("addExp", &CCreature::addExp, "Add experience and trigger level ups when thresholds are reached.")
        .def("getGold", &CCreature::getGold, "Return current gold.")
        .def("addGold", &CCreature::addGold, "Add gold to the creature inventory.")
        .def("takeGold", &CCreature::takeGold, "Remove gold from the creature inventory.")
        .def("takeMana", &CCreature::takeMana, "Consume mana, clamped at zero.")
        .def("useAction", &CCreature::useAction, "Use an interaction/action against another creature.")
        .def("useItem", &CCreature::useItem, "Use an inventory item if it is currently usable.")
        .def("hasItem", hasItem, "Return whether any inventory item matches predicate(item) -> bool.")
        .def("addItem", addItemByName, "Create and add an item by type id.")
        .def("addItem", addItemByObject, "Add an existing item object.")
        .def("addItems", &CCreature::addItems, "Add all items from a set to inventory.")
        .def("setItems", &CCreature::setItems, "Replace inventory items.")
        .def("getItems", &CCreature::getItems, "Return inventory items.")
        .def("setEffects", &CCreature::setEffects, "Replace active effects.")
        .def("getEffects", &CCreature::getEffects, "Return active effects.")
        .def("getActions", &CCreature::getActions, "Return available actions.")
        .def("removeItem", removeItem,
             "Remove the first inventory item matching predicate(item). Optional second arg allows quest removal.")
        .def("removeQuestItem", removeQuestItem, "Remove first matching quest item predicate from inventory.")
        .def("countItems", &CCreature::countItems, "Count inventory items by type id.");

    py::class_<CPlayer, CCreature, std::shared_ptr<CPlayer>>(m, "CPlayer", "Player-controlled creature.")
        .def("addQuest", &CPlayer::addQuest, "Add a quest to the player quest log.")
        .def("getQuests", &CPlayer::getQuests, "Return the player's active quests.")
        .def("setQuests", &CPlayer::setQuests, "Replace active quests.")
        .def("getCompletedQuests", &CPlayer::getCompletedQuests, "Return the player's completed quests.")
        .def("setCompletedQuests", &CPlayer::setCompletedQuests, "Replace completed quests.")
        .def("getPlayerClassId", &CPlayer::getPlayerClassId, "Return the player's class identity id.")
        .def("setPlayerClassId", &CPlayer::setPlayerClassId, "Set the player's class identity id.")
        .def("getRaceId", &CPlayer::getRaceId, "Return the player's race identity id.")
        .def("setRaceId", &CPlayer::setRaceId, "Set the player's race identity id.")
        .def("checkQuests", &CPlayer::checkQuests, "Move completed quests into the completed quest log.");

    py::class_<CListString, CGameObject, std::shared_ptr<CListString>>(m, "CListString", "String list wrapper object.")
        .def("addValue", &CListString::addValue, "Append a value to the list.")
        .def("getValues", &CListString::getValues, "Return list values.")
        .def("setValues", &CListString::setValues, "Replace list values.");

    py::class_<CListInt, CGameObject, std::shared_ptr<CListInt>>(m, "CListInt", "Integer list wrapper object.")
        .def("addValue", &CListInt::addValue, "Append a value to the list.")
        .def("getValues", &CListInt::getValues, "Return list values.")
        .def("setValues", &CListInt::setValues, "Replace list values.");

    py::class_<CMapStringString, CGameObject, std::shared_ptr<CMapStringString>>(m, "CMapStringString",
                                                                                 "String-to-string map wrapper.")
        .def("getValues", &CMapStringString::getValues, "Return map values.")
        .def("setValues", &CMapStringString::setValues, "Replace map values.");

    py::class_<CMapStringInt, CGameObject, std::shared_ptr<CMapStringInt>>(m, "CMapStringInt",
                                                                           "String-to-int map wrapper.")
        .def("getValues", &CMapStringInt::getValues, "Return map values.")
        .def("setValues", &CMapStringInt::setValues, "Replace map values.");

    py::class_<CMapIntString, CGameObject, std::shared_ptr<CMapIntString>>(m, "CMapIntString",
                                                                           "Int-to-string map wrapper.")
        .def("getValues", &CMapIntString::getValues, "Return map values.")
        .def("setValues", &CMapIntString::setValues, "Replace map values.");

    py::class_<CMapIntInt, CGameObject, std::shared_ptr<CMapIntInt>>(m, "CMapIntInt", "Int-to-int map wrapper.")
        .def("getValues", &CMapIntInt::getValues, "Return map values.")
        .def("setValues", &CMapIntInt::setValues, "Replace map values.");

    py::class_<CGamePanel, CGameGraphicsObject, std::shared_ptr<CGamePanel>>(m, "CGamePanel", "Base in-game GUI panel.")
        .def("refreshViews", &CGamePanel::refreshViews, "Refresh list views contained by the panel.")
        .def("close", &CGamePanel::close, "Close this panel.");

    py::class_<CGameTradePanel, CGamePanel, std::shared_ptr<CGameTradePanel>>(m, "CGameTradePanel", "Trade panel.")
        .def("getMarket", &CGameTradePanel::getMarket, "Return market displayed by this panel.")
        .def("setMarket", &CGameTradePanel::setMarket, "Set market displayed by this panel.")
        .def("getTotalSellCost", &CGameTradePanel::getTotalSellCost, "Return selected inventory sell total.")
        .def("getTotalBuyCost", &CGameTradePanel::getTotalBuyCost, "Return selected market buy total.");

    py::class_<CGameFightPanel, CGamePanel, std::shared_ptr<CGameFightPanel>>(m, "CGameFightPanel", "Fight panel.")
        .def("getEnemy", &CGameFightPanel::getEnemy, "Return current enemy creature.")
        .def("setEnemy", &CGameFightPanel::setEnemy, "Set current enemy creature.")
        .def("getCombatStatus", &CGameFightPanel::getCombatStatus, "Return current combat status text.")
        .def("isCancelled", &CGameFightPanel::isCancelled, "Return whether action selection was cancelled.")
        .def("cancel", &CGameFightPanel::cancel, "Cancel pending action selection.")
        .def("close", &CGameFightPanel::close, "Cancel action selection and close this fight panel.")
        .def(
            "setEnemies",
            [](CGameFightPanel &self, const py::iterable &creatures) {
                self.setEnemies(creature_iterable_to_vector(creatures));
            },
            "Set available enemy creatures.")
        .def("selectInteraction", &CGameFightPanel::selectInteraction, "Wait for and return selected interaction.")
        .def(
            "interactionsCollection",
            [](CGameFightPanel &self, const std::shared_ptr<CGui> &gui) {
                return list_view_collection_to_py(self.interactionsCollection(gui));
            },
            "Return player interactions shown by the fight panel.")
        .def("interactionsCallback", &CGameFightPanel::interactionsCallback, "Handle interaction selection.")
        .def("interactionsSelect", &CGameFightPanel::interactionsSelect, "Return whether interaction is selected.")
        .def(
            "itemsCollection",
            [](CGameFightPanel &self, const std::shared_ptr<CGui> &gui) {
                return list_view_collection_to_py(self.itemsCollection(gui));
            },
            "Return player items shown by the fight panel.")
        .def("itemsCallback", &CGameFightPanel::itemsCallback, "Handle item selection.")
        .def("itemsRightClickCallback", &CGameFightPanel::itemsRightClickCallback, "Handle direct item use.")
        .def("itemsSelect", &CGameFightPanel::itemsSelect, "Return whether an item is selected.")
        .def(
            "enemiesCollection",
            [](CGameFightPanel &self, const std::shared_ptr<CGui> &gui) {
                return list_view_collection_to_py(self.enemiesCollection(gui));
            },
            "Return enemies shown by the fight panel.")
        .def("enemiesCallback", &CGameFightPanel::enemiesCallback, "Handle enemy selection.")
        .def("enemiesSelect", &CGameFightPanel::enemiesSelect, "Return whether an enemy is selected.");

    py::class_<CGameCharacterPanel, CGamePanel, std::shared_ptr<CGameCharacterPanel>>(m, "CGameCharacterPanel",
                                                                                      "Character sheet panel.");

    py::class_<CGameQuestionPanel, CGamePanel, std::shared_ptr<CGameQuestionPanel>>(m, "CGameQuestionPanel",
                                                                                    "Question/choice panel.");

    py::class_<CGameDialogPanel, CGamePanel, std::shared_ptr<CGameDialogPanel>>(m, "CGameDialogPanel",
                                                                                "Dialog conversation panel.");

    py::class_<CGameInventoryPanel, CGamePanel, std::shared_ptr<CGameInventoryPanel>>(m, "CGameInventoryPanel",
                                                                                      "Inventory panel.");

    py::class_<CGameQuestPanel, CGamePanel, std::shared_ptr<CGameQuestPanel>>(m, "CGameQuestPanel", "Quest log panel.")
        .def("getText", &CGameQuestPanel::getText, "Return rendered quest journal text.");

    py::class_<CGameTextPanel, CGamePanel, std::shared_ptr<CGameTextPanel>>(m, "CGameTextPanel", "Text display panel.")
        .def("getText", &CGameTextPanel::getText, "Return panel text.")
        .def("setText", &CGameTextPanel::setText, "Set panel text.")
        .def("getCentered", &CGameTextPanel::getCentered, "Return whether text is centered.")
        .def("setCentered", &CGameTextPanel::setCentered, "Set whether text is centered.");

    py::class_<CListView, CProxyTargetGraphicsObject, std::shared_ptr<CListView>>(m, "CListView", "List view widget.")
        .def("getCollection", &CListView::getCollection, "Return parent collection callback name.")
        .def("setCollection", &CListView::setCollection, "Set parent collection callback name.")
        .def("getCallback", &CListView::getCallback, "Return parent click callback name.")
        .def("setCallback", &CListView::setCallback, "Set parent click callback name.")
        .def("getRightClickCallback", &CListView::getRightClickCallback, "Return parent right-click callback name.")
        .def("setRightClickCallback", &CListView::setRightClickCallback, "Set parent right-click callback name.")
        .def("getDragStart", &CListView::getDragStart, "Return parent drag-start callback name.")
        .def("setDragStart", &CListView::setDragStart, "Set parent drag-start callback name.")
        .def("getDragValidate", &CListView::getDragValidate, "Return parent drag-validation callback name.")
        .def("setDragValidate", &CListView::setDragValidate, "Set parent drag-validation callback name.")
        .def("getDrop", &CListView::getDrop, "Return parent drop callback name.")
        .def("setDrop", &CListView::setDrop, "Set parent drop callback name.")
        .def("getDragCancel", &CListView::getDragCancel, "Return parent drag-cancel callback name.")
        .def("setDragCancel", &CListView::setDragCancel, "Set parent drag-cancel callback name.")
        .def("getSelect", &CListView::getSelect, "Return parent selection callback name.")
        .def("setSelect", &CListView::setSelect, "Set parent selection callback name.")
        .def("getXPrefferedSize", &CListView::getXPrefferedSize, "Return preferred X cell count.")
        .def("setXPrefferedSize", &CListView::setXPrefferedSize, "Set preferred X cell count.")
        .def("getYPrefferedSize", &CListView::getYPrefferedSize, "Return preferred Y cell count.")
        .def("setYPrefferedSize", &CListView::setYPrefferedSize, "Set preferred Y cell count.")
        .def("getTileSize", &CListView::getTileSize, "Return list tile size.")
        .def("setTileSize", &CListView::setTileSize, "Set list tile size.")
        .def("getAllowOversize", &CListView::getAllowOversize, "Return whether list scroll arrows are enabled.")
        .def("setAllowOversize", &CListView::setAllowOversize, "Set whether list scroll arrows are enabled.")
        .def("getShowEmpty", &CListView::getShowEmpty, "Return whether empty cells render boxes.")
        .def("setShowEmpty", &CListView::setShowEmpty, "Set whether empty cells render boxes.")
        .def("getGrouping", &CListView::getGrouping, "Return whether repeated type ids are grouped.")
        .def("setGrouping", &CListView::setGrouping, "Set whether repeated type ids are grouped.")
        .def(
            "getRuntimeGridSize",
            [](CListView &self, const std::shared_ptr<CGui> &gui) {
                return py::make_tuple(self.getSizeX(gui), self.getSizeY(gui));
            },
            "Return resolved list grid size as (columns, rows).");
    PY_WRAP_GENERIC_DOC(randint, "randint(lower, upper) -> int: Return a random integer in engine-defined bounds.");
    m.def("jsonify", &jsonify_py, "jsonify(obj) -> str: Serialize a game object to JSON text.");
    PY_WRAP_GENERIC_DOC(logger, "logger(message) -> None: Write an info log message to the engine logger.");
    m.def("set_logger_sink", set_logger_sink_py, py::arg("sink_name"), py::arg("path") = py::none(),
          "set_logger_sink(sink, path=None) -> None: Configure the native logger output target.");
    m.def("configure_playtest_trace", configure_playtest_trace_py, py::arg("enabled") = true,
          py::arg("output_path") = py::none(), py::arg("max_records") = 1000,
          "configure_playtest_trace(enabled=True, output_path=None, max_records=1000) -> None: Configure structured "
          "playtest trace collection.");
    m.def("configure_playtest_trace_from_env", &CPlaytestTrace::configureFromEnvironment,
          "Configure playtest tracing from GAME_PLAYTEST_TRACE.");
    m.def("playtest_trace_enabled", &CPlaytestTrace::enabled,
          "playtest_trace_enabled() -> bool: Return whether structured playtest tracing is enabled.");
    m.def("clear_playtest_trace", &CPlaytestTrace::clear,
          "clear_playtest_trace() -> None: Clear collected playtest trace records.");
    m.def("get_playtest_trace_records", &CPlaytestTrace::records,
          "get_playtest_trace_records() -> list[str]: Return collected JSONL playtest trace records.");
    m.def("drain_playtest_trace_records", &CPlaytestTrace::drain,
          "drain_playtest_trace_records() -> list[str]: Return and clear collected JSONL playtest trace records.");
    m.def("record_playtest_trace_json", &CPlaytestTrace::recordJson, py::arg("event"), py::arg("fields_json") = "{}",
          "record_playtest_trace_json(event, fields_json='{}') -> None: Add one structured playtest trace record.");
}

#if !defined(_WIN32)
PYBIND11_MODULE(_game, m) { init_game_module(m); }
#endif
