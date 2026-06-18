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
#include "core/CSaveFormat.h"
#include "core/CJsonUtil.h"

#include <algorithm>
#include <cctype>

namespace CSaveFormat {

bool isValidMapName(const std::string &mapName) {
    if (mapName.empty()) {
        return true;
    }

    return std::all_of(mapName.begin(), mapName.end(), [](unsigned char ch) {
        if (std::isalnum(ch)) {
            return true;
        }
        return ch == '_' || ch == '-';
    });
}

bool isValidSlotName(const std::string &slotName) {
    if (slotName.empty() || slotName.front() == '.' || slotName.find("..") != std::string::npos) {
        return false;
    }

    return std::all_of(slotName.begin(), slotName.end(), [](unsigned char ch) {
        if (std::isalnum(ch)) {
            return true;
        }
        return ch == '.' || ch == '_' || ch == '-';
    });
}

std::string savedMapConfigKey(const std::string &slotName) { return "__save_slot__/" + slotName; }

std::string primaryPath(const std::string &slotName) { return "save/" + slotName + ".json"; }

std::string backupPath(const std::string &slotName) { return primaryPath(slotName) + BACKUP_SUFFIX; }

std::optional<std::string> primarySlotFromFilename(const std::filesystem::path &filename) {
    if (filename.extension() != ".json") {
        return std::nullopt;
    }
    const auto slotName = filename.stem().string();
    if (!isValidSlotName(slotName)) {
        return std::nullopt;
    }
    return slotName;
}

std::optional<std::string> backupSlotFromFilename(const std::filesystem::path &filename) {
    if (filename.extension() != BACKUP_SUFFIX) {
        return std::nullopt;
    }
    auto primaryName = filename.stem();
    if (primaryName.extension() != ".json") {
        return std::nullopt;
    }
    const auto slotName = primaryName.stem().string();
    if (!isValidSlotName(slotName)) {
        return std::nullopt;
    }
    return slotName;
}

std::optional<std::string> readSnapshotMapName(const std::shared_ptr<json> &snapshot) {
    if (!snapshot || !snapshot->is_object() || !snapshot->contains("class") || !(*snapshot)["class"].is_string() ||
        (*snapshot)["class"].get<std::string>() != "CMap" || !snapshot->contains("properties") ||
        !(*snapshot)["properties"].is_object() || !(*snapshot)["properties"].contains("mapName") ||
        !(*snapshot)["properties"]["mapName"].is_string()) {
        return std::nullopt;
    }
    return (*snapshot)["properties"]["mapName"].get<std::string>();
}

std::expected<DecodedDocument, std::string> decodeDocument(const std::shared_ptr<json> &document) {
    if (!document || !document->is_object()) {
        return std::unexpected("save root is not a JSON object");
    }

    if (document->contains("format")) {
        if (!(*document)["format"].is_string() || (*document)["format"].get<std::string>() != FORMAT) {
            return std::unexpected("unsupported save format");
        }
        if (!document->contains("schemaVersion") || !(*document)["schemaVersion"].is_number_integer()) {
            return std::unexpected("save envelope is missing integer schemaVersion");
        }
        const int schemaVersion = (*document)["schemaVersion"].get<int>();
        if (schemaVersion > SCHEMA_VERSION) {
            return std::unexpected("save schema version is newer than this game build");
        }
        if (schemaVersion != SCHEMA_VERSION) {
            return std::unexpected("unsupported save schema version");
        }
        if (!document->contains("mapName") || !(*document)["mapName"].is_string()) {
            return std::unexpected("save envelope is missing string mapName");
        }
        const auto mapName = (*document)["mapName"].get<std::string>();
        if (!isValidMapName(mapName)) {
            return std::unexpected("save envelope contains invalid mapName");
        }
        if (!document->contains("snapshot") || !(*document)["snapshot"].is_object()) {
            return std::unexpected("save envelope is missing object snapshot");
        }
        auto snapshot = CJsonUtil::alias(document, (*document)["snapshot"]);
        auto snapshotMapName = readSnapshotMapName(snapshot);
        if (!snapshotMapName) {
            return std::unexpected("save snapshot is missing a valid CMap mapName");
        }
        if (*snapshotMapName != mapName) {
            return std::unexpected("save envelope mapName does not match snapshot mapName");
        }
        return DecodedDocument{snapshot, mapName, Encoding::Versioned};
    }

    auto legacyMapName = readSnapshotMapName(document);
    if (!legacyMapName) {
        return std::unexpected("legacy save is missing a valid CMap mapName");
    }
    if (!isValidMapName(*legacyMapName)) {
        return std::unexpected("legacy save contains invalid mapName");
    }
    return DecodedDocument{document, *legacyMapName, Encoding::Legacy};
}

std::expected<std::shared_ptr<json>, std::string> buildEnvelope(const std::shared_ptr<json> &snapshot,
                                                                const std::string &expectedMapName) {
    auto snapshotMapName = readSnapshotMapName(snapshot);
    if (!snapshotMapName) {
        return std::unexpected("snapshot is missing a valid CMap mapName");
    }
    if (*snapshotMapName != expectedMapName) {
        return std::unexpected("snapshot mapName does not match active mapName");
    }
    if (!isValidMapName(*snapshotMapName)) {
        return std::unexpected("snapshot contains invalid mapName");
    }

    auto envelope = std::make_shared<json>();
    (*envelope)["format"] = FORMAT;
    (*envelope)["schemaVersion"] = SCHEMA_VERSION;
    (*envelope)["mapName"] = *snapshotMapName;
    (*envelope)["snapshot"] = *snapshot;
    return envelope;
}

} // namespace CSaveFormat
