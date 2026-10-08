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
#include "object/CCreatureClass.h"
#include "object/CCreatureRace.h"
#include "object/CGameObject.h"
#include "object/CItem.h"

#include <cstdlib>
#include <deque>
#include <filesystem>
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
    bool retainRecent = false;
    bool outputFailed = false;
    bool recordFailureReported = false;
    std::size_t fileRecords = 0;
    std::deque<std::string> records;
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
    std::size_t length = MAX_FIELD_LENGTH;
    while (length > 0 && (static_cast<unsigned char>(value[length]) & 0xC0) == 0x80) {
        --length;
    }
    value.resize(length);
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

void failOutput(TraceState &current, const char *reason) noexcept {
    current.outputFailed = true;
    try {
        std::cerr << "Playtest trace output unavailable; retaining memory history: "
                  << current.outputTarget.substr(0, 512) << " (" << reason << ")\n";
    } catch (...) {
    }
}

void failRecording() noexcept {
    try {
        std::lock_guard lock(state().mutex);
        if (state().recordFailureReported) {
            return;
        }
        state().recordFailureReported = true;
        std::cerr << "Playtest trace record unavailable; gameplay continues with retained history\n";
    } catch (...) {
    }
}

void validateFreshTarget(TraceState &current) noexcept {
    if (current.outputTarget.empty() || isStdStreamTarget(current.outputTarget)) {
        return;
    }
    try {
        const std::filesystem::path target(current.outputTarget);
        std::error_code error;
        const auto status = std::filesystem::symlink_status(target, error);
        if (status.type() != std::filesystem::file_type::not_found &&
            (error || !std::filesystem::is_regular_file(status))) {
            failOutput(current, "destination is not a regular file");
            return;
        }
        if (std::filesystem::exists(status)) {
            const auto size = std::filesystem::file_size(target, error);
            if (error || size != 0) {
                failOutput(current, "recent history requires a fresh destination");
                return;
            }
        }
        const auto backupStatus = std::filesystem::symlink_status(current.outputTarget + ".1", error);
        if (backupStatus.type() != std::filesystem::file_type::not_found) {
            failOutput(current, "recent history backup already exists or cannot be checked");
        }
    } catch (...) {
        failOutput(current, "destination could not be checked");
    }
}

void writeTarget(TraceState &current, const std::string &line) noexcept {
    if (current.outputTarget.empty() || current.outputFailed) {
        return;
    }
    try {
        if (current.outputTarget == "stdout") {
            std::cout << line << '\n';
            if (!std::cout) {
                failOutput(current, "stdout write failed");
            }
            return;
        }
        if (current.outputTarget == "stderr") {
            std::cerr << line << '\n';
            if (!std::cerr) {
                failOutput(current, "stderr write failed");
            }
            return;
        }
        const std::filesystem::path target(current.outputTarget);
        if (current.retainRecent && current.fileRecords >= current.maxRecords) {
            const std::filesystem::path backup(current.outputTarget + ".1");
            std::error_code error;
            const auto backupStatus = std::filesystem::symlink_status(backup, error);
            if (backupStatus.type() != std::filesystem::file_type::not_found) {
                if (error || !std::filesystem::is_regular_file(backupStatus)) {
                    failOutput(current, "backup cannot be rotated");
                    return;
                }
                std::filesystem::remove(backup, error);
                if (error) {
                    failOutput(current, "backup could not be removed");
                    return;
                }
            }
            std::filesystem::rename(target, backup, error);
            if (error) {
                failOutput(current, "destination could not be rotated");
                return;
            }
            current.fileRecords = 0;
        }
        std::ofstream out(target, std::ios::app);
        if (!out) {
            failOutput(current, "file could not be opened");
            return;
        }
        out << line << '\n';
        out.close();
        if (!out) {
            failOutput(current, "file write failed");
            return;
        }
        ++current.fileRecords;
    } catch (...) {
        failOutput(current, "output operation failed");
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

    const char *rawRetainRecent = std::getenv("GAME_PLAYTEST_TRACE_RETAIN_RECENT");
    configure(true, outputTarget, DEFAULT_MAX_RECORDS, rawRetainRecent && !isDisabledValue(rawRetainRecent));
}

void CPlaytestTrace::configure(bool enabled, const std::string &outputTarget, std::size_t maxRecords,
                               bool retainRecent) {
    std::lock_guard lock(state().mutex);
    state().enabled = enabled;
    state().outputTarget = outputTarget;
    state().maxRecords = maxRecords == 0 ? DEFAULT_MAX_RECORDS : maxRecords;
    state().records.clear();
    state().nextSeq = 1;
    state().truncated = false;
    state().retainRecent = retainRecent;
    state().outputFailed = false;
    state().recordFailureReported = false;
    state().fileRecords = 0;
    if (enabled && retainRecent) {
        validateFreshTarget(state());
    }
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
    return {state().records.begin(), state().records.end()};
}

std::vector<std::string> CPlaytestTrace::drain() {
    std::lock_guard lock(state().mutex);
    std::vector<std::string> result(state().records.begin(), state().records.end());
    state().records.clear();
    state().truncated = false;
    return result;
}

void CPlaytestTrace::record(const std::string &event, json fields) noexcept try {
    std::lock_guard lock(state().mutex);
    if (!state().enabled) {
        return;
    }

    std::string line;
    fields["event"] = event;
    fields["schema"] = "playtest_trace.v1";
    fields["seq"] = static_cast<unsigned long long>(state().nextSeq++);
    line = fields.dump();
    if (state().retainRecent) {
        if (state().records.size() == state().maxRecords) {
            state().records.pop_front();
        }
        state().records.push_back(line);
    } else if (state().records.size() < state().maxRecords) {
        state().records.push_back(line);
    } else if (!state().truncated) {
        const auto truncated = truncatedRecord(state().nextSeq++, state().maxRecords).dump();
        state().records.push_back(truncated);
        state().truncated = true;
        line = truncated;
    } else {
        return;
    }
    writeTarget(state(), line);
} catch (...) {
    failRecording();
}

void CPlaytestTrace::recordJson(const std::string &event, const std::string &fieldsJson) noexcept try {
    if (!enabled()) {
        return;
    }
    json fields = fieldsJson.empty() ? json::object() : json::parse(fieldsJson);
    if (!fields.is_object()) {
        fields = json::object();
    }
    record(event, fields);
} catch (...) {
    failRecording();
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
        // The "id"/"typeId" above already capture the concrete spawn/template id.
        // Record the archetype race/class definition ids separately so traces can
        // distinguish the spawned creature from its race/class archetypes. These
        // stay empty on legacy (non-archetype) creatures that carry no definition.
        if (auto race = creature->getRace()) {
            ref["raceId"] = truncateValue(race->getTypeId());
        } else {
            ref["raceId"] = "";
        }
        if (auto creatureClass = creature->getCreatureClass()) {
            ref["classId"] = truncateValue(creatureClass->getTypeId());
        } else {
            ref["classId"] = "";
        }
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
