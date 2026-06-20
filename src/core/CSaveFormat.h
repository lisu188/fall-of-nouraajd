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
#pragma once

#include "core/CGlobal.h"

namespace CSaveFormat {

inline constexpr const char *FORMAT = "fall-of-nouraajd-save";
inline constexpr int SCHEMA_VERSION = 1;
inline constexpr const char *BACKUP_SUFFIX = ".bak";

enum class Encoding { Versioned, Legacy };

struct DecodedDocument {
    std::shared_ptr<json> snapshot;
    std::string mapName;
    Encoding encoding = Encoding::Versioned;
};

bool isValidMapName(const std::string &mapName);

bool isValidSlotName(const std::string &slotName);

std::string savedMapConfigKey(const std::string &slotName);

std::string primaryPath(const std::string &slotName);

std::string backupPath(const std::string &slotName);

std::optional<std::string> primarySlotFromFilename(const std::filesystem::path &filename);

std::optional<std::string> backupSlotFromFilename(const std::filesystem::path &filename);

std::optional<std::string> readSnapshotMapName(const std::shared_ptr<json> &snapshot);

// Decodes every supported on-disk save shape through the schema migration registry and returns the
// current in-memory snapshot shape consumed by strict CSerialization deserialization.
std::expected<DecodedDocument, std::string> decodeDocument(const std::shared_ptr<json> &document);

std::expected<std::shared_ptr<json>, std::string> buildEnvelope(const std::shared_ptr<json> &snapshot,
                                                                const std::string &expectedMapName);

} // namespace CSaveFormat
