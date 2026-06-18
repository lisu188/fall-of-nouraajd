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
#include "core/CPlaytestTrace.h"

#include "core/CMap.h"
#include "object/CCreature.h"
#include "object/CGameObject.h"
#include "object/CItem.h"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <mutex>

namespace {
constexpr std::size_t DEFAULT_MAX_RECORDS = 1000;
constexpr std::size_t MAX_FIELD_LENGTH = 160;

struct TraceState {
    bool enabled = false;
    std::string outputTarget;
    std::size_t maxRecords = DEFAULT_MAX_RECORDS;
    std::size_t nextSeq = 1;
    bool truncated = false;
    std::vector<std::string> records;
    std::mutex mutex;
};

TraceState &state() {
    static TraceState current;
    return current;
}

bool isDisabledValue(const std::string &value) {
    return value.empty() || value == "0" || value == "false" || value == "FALSE" || value == "off" || value == "OFF" ||
           value == "disabled" || value == "DISABLED";
}

bool isStdStreamTarget(const std::string &target) { return target == "stdout" || target == "stderr"; }

std::string truncateValue(std::string value) {
    if (value.size() <= MAX_FIELD_LENGTH) {
        return value;
    }
    value.resize(MAX_FIELD_LENGTH);
    return value;
}

std::string stableObjectId(const std::shared_ptr<CGameObject> &object) {
    if (!object) {
        return "";
    }
    const auto typeId = object->getTypeId();
    if (!typeId.empty()) {
        return truncateValue(typeId);
    }
    const auto name = object->getName();
    if (!name.empty()) {
        return truncateValue(name);
    }
    return truncateValue(object->getType());
}

std::string stableObjectType(const std::shared_ptr<CGameObject> &object) {
    if (!object) {
        return "";
    }
    const auto type = object->getType();
    return truncateValue(type.empty() ? object->getTypeId() : type);
}

std::string mapName(const std::shared_ptr<CMap> &map) {
    if (!map) {
        return "";
    }
    const auto explicitName = map->getMapName();
    if (!explicitName.empty()) {
        return truncateValue(explicitName);
    }
    return stableObjectId(map);
}

void writeTarget(const std::string &target, const std::string &line) {
    if (target.empty()) {
        return;
    }
    if (target == "stdout") {
        std::cout << line << '\n';
        return;
    }
    if (target == "stderr") {
        std::cerr << line << '\n';
        return;
    }
    std::ofstream out(target, std::ios::app);
    if (out) {
        out << line << '\n';
    }
}

json truncatedRecord(std::size_t seq, std::size_t maxRecords) {
    return {
        {"event", "trace_truncated"},
        {"maxRecords", static_cast<unsigned long long>(maxRecords)},
        {"schema", "playtest_trace.v1"},
        {"seq", static_cast<unsigned long long>(seq)},
        {"truncated", true},
    };
}
} // namespace

void CPlaytestTrace::configureFromEnvironment() {
    const char *rawEnabled = std::getenv("GAME_PLAYTEST_TRACE");
    if (!rawEnabled || isDisabledValue(rawEnabled)) {
        configure(false);
        return;
    }

    const std::string enabledValue = rawEnabled;
    std::string outputTarget;
    if (const char *rawFile = std::getenv("GAME_PLAYTEST_TRACE_FILE")) {
        outputTarget = rawFile;
    } else if (isStdStreamTarget(enabledValue)) {
        outputTarget = enabledValue;
    } else if (enabledValue != "1" && enabledValue != "true" && enabledValue != "TRUE" && enabledValue != "on" &&
               enabledValue != "ON" && enabledValue != "enabled" && enabledValue != "ENABLED") {
        outputTarget = enabledValue;
    } else {
        outputTarget = "stderr";
    }

    configure(true, outputTarget, DEFAULT_MAX_RECORDS);
}

void CPlaytestTrace::configure(bool enabled, const std::string &outputTarget, std::size_t maxRecords) {
    std::lock_guard lock(state().mutex);
    state().enabled = enabled;
    state().outputTarget = outputTarget;
    state().maxRecords = maxRecords == 0 ? DEFAULT_MAX_RECORDS : maxRecords;
    state().records.clear();
    state().nextSeq = 1;
    state().truncated = false;
}

bool CPlaytestTrace::enabled() {
    std::lock_guard lock(state().mutex);
    return state().enabled;
}

void CPlaytestTrace::clear() {
    std::lock_guard lock(state().mutex);
    state().records.clear();
    state().nextSeq = 1;
    state().truncated = false;
}

std::vector<std::string> CPlaytestTrace::records() {
    std::lock_guard lock(state().mutex);
    return state().records;
}

std::vector<std::string> CPlaytestTrace::drain() {
    std::lock_guard lock(state().mutex);
    auto result = state().records;
    state().records.clear();
    state().truncated = false;
    return result;
}

void CPlaytestTrace::record(const std::string &event, json fields) {
    if (!enabled()) {
        return;
    }

    std::string line;
    std::string target;
    {
        std::lock_guard lock(state().mutex);
        if (!state().enabled) {
            return;
        }

        fields["event"] = event;
        fields["schema"] = "playtest_trace.v1";
        fields["seq"] = static_cast<unsigned long long>(state().nextSeq++);
        line = fields.dump();
        target = state().outputTarget;

        if (state().records.size() < state().maxRecords) {
            state().records.push_back(line);
        } else if (!state().truncated) {
            const auto truncated = truncatedRecord(state().nextSeq++, state().maxRecords).dump();
            state().records.push_back(truncated);
            state().truncated = true;
            line = truncated;
        } else {
            return;
        }
    }

    writeTarget(target, line);
}

void CPlaytestTrace::recordJson(const std::string &event, const std::string &fieldsJson) {
    json fields = fieldsJson.empty() ? json::object() : json::parse(fieldsJson);
    if (!fields.is_object()) {
        fields = json::object();
    }
    record(event, fields);
}

json CPlaytestTrace::coords(Coords coords) {
    return {
        {"x", coords.x},
        {"y", coords.y},
        {"z", coords.z},
    };
}

json CPlaytestTrace::objectRef(const std::shared_ptr<CGameObject> &object) {
    if (!object) {
        return json();
    }

    json ref = {
        {"id", stableObjectId(object)},
        {"name", truncateValue(object->getName())},
        {"type", stableObjectType(object)},
        {"typeId", truncateValue(object->getTypeId())},
    };
    if (auto creature = std::dynamic_pointer_cast<CCreature>(object)) {
        ref["isPlayer"] = creature->isPlayer();
    }
    return ref;
}

json CPlaytestTrace::objectRefs(const std::vector<std::shared_ptr<CCreature>> &objects) {
    json refs = json::array();
    std::size_t index = 0;
    for (const auto &object : objects) {
        refs[index++] = objectRef(object);
    }
    return refs;
}

json CPlaytestTrace::itemRefs(const std::set<std::shared_ptr<CItem>> &items) {
    json refs = json::array();
    std::size_t index = 0;
    for (const auto &item : items) {
        refs[index++] = objectRef(item);
    }
    return refs;
}

void CPlaytestTrace::addMapContext(json &fields, const std::shared_ptr<CMap> &map) {
    if (!map) {
        return;
    }
    fields["map"] = mapName(map);
    fields["turn"] = map->getTurn();
}
