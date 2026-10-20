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
#include "core/CPlaytestTrace.h"
#include "core/CRuntimeBridge.h"
#include "gui/panel/CGameCampaignBrowserPanel.h"
#include "gui/panel/CGameCampaignPanel.h"
#include "gui/panel/CGameCharacterPanel.h"
#include "gui/panel/CGameDialogPanel.h"
#include "gui/panel/CGameFightPanel.h"
#include "gui/panel/CGameInventoryPanel.h"
#include "gui/panel/CGameQuestPanel.h"
#include "gui/panel/CGameQuestionPanel.h"
#include "gui/panel/CGameTextPanel.h"
#include "gui/panel/CGameTradePanel.h"
#include "object/CObject.h"
#include <cctype>

namespace py = pybind11;

namespace nouraajd::bindings {
namespace {
std::string jsonify(std::shared_ptr<CGameObject> x) { return JSONIFY(x); }

std::string jsonify_py(const py::handle &value) {
    if (py::isinstance<CGameObject>(value)) {
        return jsonify(value.cast<std::shared_ptr<CGameObject>>());
    }
    throw py::type_error("jsonify() expects a CGameObject instance");
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
                                 std::size_t max_records = 1000, bool retain_recent = false) {
    std::string target;
    if (!output_path.is_none()) {
        target = output_path.cast<std::string>();
    }
    CPlaytestTrace::configure(enabled, target, max_records, retain_recent);
}

py::list list_view_collection_to_py(const CListView::collection_pointer &collection) {
    py::list objects;
    for (const auto &object : *collection) {
        objects.append(object);
    }
    return objects;
}
} // namespace

#define PY_WRAP_GENERIC_DOC(fcn, doc) m.def(#fcn, fcn, doc)

void bindPanelsAndUtilities(py::module_ &m) {
    py::class_<CGamePanel, CGameGraphicsObject, std::shared_ptr<CGamePanel>>(m, "CGamePanel", "Base in-game GUI panel.")
        .def("refreshViews", &CGamePanel::refreshViews, "Refresh list views contained by the panel.")
        .def("setTitle", &CGamePanel::setTitle)
        .def("setCloseable", &CGamePanel::setCloseable)
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

    py::class_<CGameCampaignPanel, CGamePanel, std::shared_ptr<CGameCampaignPanel>>(
        m, "CGameCampaignPanel", "Full-window blocking campaign presentation screen.")
        .def("getTitle", &CGameCampaignPanel::getTitle, "Return the screen title.")
        .def("getBody", &CGameCampaignPanel::getBody, "Return the screen body text.")
        .def("getActionLabel", &CGameCampaignPanel::getActionLabel, "Return the action button label.")
        .def("isDismissed", &CGameCampaignPanel::isDismissed, "Return whether the action dismissed the screen.")
        .def("clickAction", &CGameCampaignPanel::clickAction, "Dismiss the screen via its action.");

    py::class_<CGameCampaignBrowserPanel, CGamePanel, std::shared_ptr<CGameCampaignBrowserPanel>>(
        m, "CGameCampaignBrowserPanel", "Stable-ID two-column campaign browser panel.")
        .def("getSelectedId", &CGameCampaignBrowserPanel::getSelectedId, "Return the highlighted campaign id.")
        .def("getDetailText", &CGameCampaignBrowserPanel::getDetailText, "Return the rendered detail text.")
        .def("hasChoice", &CGameCampaignBrowserPanel::hasChoice, "Return whether the browser resolved a choice.")
        .def("clickSelect", &CGameCampaignBrowserPanel::clickSelect, "Confirm the highlighted campaign.")
        .def("clickCancel", &CGameCampaignBrowserPanel::clickCancel, "Cancel the browser with an empty id.");

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
        .def("getRows", &CListView::getRows, "Return whether the list displays named rows.")
        .def("getCellSize", &CListView::getCellSize, "Return the scaled row height or grid cell size.")
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
    PY_WRAP_GENERIC_DOC(randint, "randint(lower, upper) -> int: Return a uniform integer with both bounds inclusive. "
                                 "Reversed bounds are normalized.");
    m.def("_seedRandomForTests", [](std::uint32_t seed) { seedModuleRandomForTests(seed); }, py::arg("seed"));
    m.def("jsonify", &jsonify_py, "jsonify(obj) -> str: Serialize a game object to JSON text.");
    PY_WRAP_GENERIC_DOC(logger, "logger(message) -> None: Write an info log message to the engine logger.");
    m.def("set_logger_sink", set_logger_sink_py, py::arg("sink_name"), py::arg("path") = py::none(),
          "set_logger_sink(sink, path=None) -> None: Configure the native logger output target.");
    m.def("configure_playtest_trace", configure_playtest_trace_py, py::arg("enabled") = true,
          py::arg("output_path") = py::none(), py::arg("max_records") = 1000, py::arg("retain_recent") = false,
          "configure_playtest_trace(enabled=True, output_path=None, max_records=1000, retain_recent=False) -> None: "
          "Configure structured playtest tracing. Recent history keeps the latest records and rotates a fresh file "
          "to one .1 backup; output failures retain memory history.");
    m.def("configure_playtest_trace_from_env", &CPlaytestTrace::configureFromEnvironment,
          "Configure playtest tracing from GAME_PLAYTEST_TRACE.");
    m.def("playtest_trace_enabled", &CPlaytestTrace::enabled,
          "playtest_trace_enabled() -> bool: Return whether structured playtest tracing is enabled.");
    m.def("playtest_trace_output_available", &CPlaytestTrace::outputAvailable,
          "playtest_trace_output_available() -> bool: Return whether tracing has configured output with no detected "
          "failure. This does not probe the filesystem or reset output failures.");
    m.def("clear_playtest_trace", &CPlaytestTrace::clear,
          "clear_playtest_trace() -> None: Clear collected playtest trace records.");
    m.def("get_playtest_trace_records", &CPlaytestTrace::records,
          "get_playtest_trace_records() -> list[str]: Return collected JSONL playtest trace records.");
    m.def("drain_playtest_trace_records", &CPlaytestTrace::drain,
          "drain_playtest_trace_records() -> list[str]: Return and clear collected JSONL playtest trace records.");
    m.def("record_playtest_trace_json", &CPlaytestTrace::recordJson, py::arg("event"), py::arg("fields_json") = "{}",
          "record_playtest_trace_json(event, fields_json='{}') -> None: Add one structured playtest trace record.");
}

#undef PY_WRAP_GENERIC_DOC
} // namespace nouraajd::bindings
