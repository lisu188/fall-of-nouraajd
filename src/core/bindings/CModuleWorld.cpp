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
#include "CModuleBindings.h"
#include "gui/panel/CGamePanel.h"
#include "gui/panel/CGameDialogPanel.h"
#include "object/CDialog.h"
#include "core/CController.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"
#include "gui/CAnimation.h"
#include "gui/CGui.h"
#include "gui/CLayout.h"
#include "gui/object/CMapGraphicsObject.h"
#include "gui/object/CMinimapGraphicsObject.h"
#include "gui/object/CSideBar.h"
#include "gui/object/CStatsGraphicsObject.h"
#include "gui/panel/CCreatureView.h"
#include "object/CObject.h"

namespace py = pybind11;

namespace nouraajd::bindings {
namespace {
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
} // namespace

void bindGraphicsAndWorld(py::module_ &m) {
    py::class_<CGameGraphicsObject, CGameObject, std::shared_ptr<CGameGraphicsObject>>(
        m, "CGameGraphicsObject", "Base class for GUI graphics objects.")
        .def("getGui", &CGameGraphicsObject::getGui, "Return the owning GUI object.")
        .def("isVisible", &CGameGraphicsObject::isVisible, "Return current visibility including responsive layout.")
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
            [](CGameGraphicsObject &self) -> py::tuple {
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
        .def("getUiPreferences", &CGui::getUiPreferences)
        .def("applyUiPreferences", &CGui::applyUiPreferences)
        .def("getUiScale", &CGui::getUiScale)
        .def("getTextScale", &CGui::getTextScale)
        .def("notify", &CGui::notify)
        .def("notifyAt", &CGui::notifyAt)
        .def("getUiHistory", &CGui::getUiHistory)
        .def("isActive", &CGui::isActive)
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
        .def("getAssignedPlayer", &CMap::getAssignedPlayer,
             "Observe the assigned player cache without recovery or mutation; engine owner thread only.")
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
        .def("isMoving", &CMap::isMoving, "Return whether a map turn is still in progress.")
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
        .def("lookupNavigationStepCost", &CMap::lookupNavigationStepCost, py::arg("fromCoords"), py::arg("toCoords"),
             "Price a graph step using destination terrain plus a registered connector surcharge.")
        .def(
            "lookupNavigationStepCost",
            [](std::shared_ptr<CMap> self, int fromX, int fromY, int fromZ, int toX, int toY, int toZ) {
                return self->lookupNavigationStepCost(Coords(fromX, fromY, fromZ), Coords(toX, toY, toZ));
            },
            py::arg("fromX"), py::arg("fromY"), py::arg("fromZ"), py::arg("toX"), py::arg("toY"), py::arg("toZ"),
            "Price a graph step from integer coordinates without creating tile handles.")
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
        .def("supportsSevenSunsMerchants", &CGuiHandler::supportsSevenSunsMerchants,
             "Whether the fixed native Seven Suns merchant dialogue and stock service is available.")
        .def("supportsSevenSunsWarning", &CGuiHandler::supportsSevenSunsWarning,
             "Whether the compiled finite Seven Suns warning UI-flow service is available.")
        .def("showMessage", &CGuiHandler::showMessage, "Show a message panel.")
        .def("showMessageLater", &CGuiHandler::showMessageLater, "Queue a session-owned message without waiting.")
        .def("waitMilliseconds", &CGuiHandler::waitMilliseconds, py::arg("state"),
             "Await a same-session serializable wait state; return true only after its duration elapses.")
        .def("getSessionSaveStatus", &CGuiHandler::getSessionSaveStatus)
        .def("setSessionSaveStatus", &CGuiHandler::setSessionSaveStatus)
        .def("notify", &CGuiHandler::notify, "Record nonblocking feedback in History.")
        .def("showChoice", &CGuiHandler::showChoice, py::arg("title"), py::arg("choicesJson"),
             py::arg("actionLabel") = "Select", py::arg("backLabel") = "Back")
        .def("showCharacterCreationOptions", &CGuiHandler::showCharacterCreationOptions, py::arg("classesJson"),
             py::arg("racesJson"))
        .def("showConfirm", &CGuiHandler::showConfirm, py::arg("title"), py::arg("body"),
             py::arg("confirmLabel") = "Confirm", py::arg("cancelLabel") = "Cancel")
        .def("showPauseMenu", &CGuiHandler::showPauseMenu)
        .def("showSaveMenu", &CGuiHandler::showSaveMenu)
        .def("showTextInput", &CGuiHandler::showTextInput, py::arg("title"), py::arg("prompt"),
             py::arg("initialValue") = "")
        .def("showLoading", &CGuiHandler::showLoading)
        .def("hideLoading", &CGuiHandler::hideLoading)
        .def("showTrade", &CGuiHandler::showTrade, "Open a trade panel.")
        .def("getRequestedTradeMarket", &CGuiHandler::getRequestedTradeMarket,
             "Return the last actual traced headless trade request in the active map and transition generation; "
             "return None after observing disabled tracing or an invalidated session.")
        .def("openDialog", &CGuiHandler::openDialog, py::arg("dialog"),
             "Open a dialog on the main thread without waiting; return the attached panel or None.")
        .def("showDialog", &CGuiHandler::showDialog, "Open a dialog panel.")
        .def("showQuestion", &CGuiHandler::showQuestion, "Open a question/choice panel.")
        .def("showSelection", &CGuiHandler::showSelection, "Open a selection panel.")
        .def("showCharacterCreation", &CGuiHandler::showCharacterCreation, py::arg("classes"), py::arg("races"),
             "Open the class+race character-creation panel; returns a (classLabel, raceLabel) tuple.")
        .def("showCampaignScreen", &CGuiHandler::showCampaignScreen, py::arg("title"), py::arg("body"),
             py::arg("actionLabel"),
             "Show a full-window blocking campaign presentation screen; headless runs log and return.")
        .def("showCampaignArtworkScreen", &CGuiHandler::showCampaignArtworkScreen, py::arg("title"), py::arg("body"),
             py::arg("actionLabel"), py::arg("artwork"), "Show a campaign screen with optional authored artwork.")
        .def("showCampaignSelection", &CGuiHandler::showCampaignSelection, py::arg("titles"), py::arg("descriptions"),
             py::arg("scenarioCounts"),
             "Show the stable-ID campaign browser; returns the confirmed campaign id or \"\" on cancel/headless.")
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
}
} // namespace nouraajd::bindings
