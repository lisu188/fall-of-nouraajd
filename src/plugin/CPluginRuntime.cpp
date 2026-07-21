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
#include "plugin/CPluginRuntime.h"
#include "core/CGlobal.h"
#include "core/CLoader.h"
#include <map>

namespace {

std::map<std::string, std::shared_ptr<IPluginRuntime>> &runtimes() {
    static std::map<std::string, std::shared_ptr<IPluginRuntime>> registry;
    return registry;
}

class CNativeKindRuntime : public IPluginRuntime {
  public:
    std::string kind() const override { return "native"; }

    bool load(const std::shared_ptr<CGame> &game, const CPluginDescriptor &descriptor) override {
        return plugin_runtime::loadNativePlugin(game, descriptor.source, descriptor.entry);
    }
};

class CCppKindRuntime : public IPluginRuntime {
  public:
    std::string kind() const override { return "cpp"; }

    bool load(const std::shared_ptr<CGame> &game, const CPluginDescriptor &descriptor) override {
        return CPluginLoader::loadCppPlugin(game, descriptor.source);
    }
};

class CPythonKindRuntime : public IPluginRuntime {
  public:
    std::string kind() const override { return "python"; }

    bool load(const std::shared_ptr<CGame> &game, const CPluginDescriptor &descriptor) override {
        return CPluginLoader::loadPlugin(game, descriptor.source);
    }
};

class CLuaKindRuntime : public IPluginRuntime {
  public:
    std::string kind() const override { return "lua"; }

    bool load(const std::shared_ptr<CGame> &game, const CPluginDescriptor &descriptor) override {
        return CPluginLoader::loadLuaPlugin(game, descriptor.source);
    }
};

} // namespace

namespace plugin_runtime {

void registerRuntime(const std::shared_ptr<IPluginRuntime> &runtime) {
    if (!runtime) {
        return;
    }
    runtimes()[runtime->kind()] = runtime;
}

IPluginRuntime *find(const std::string &kind) {
    auto found = runtimes().find(kind);
    return found == runtimes().end() ? nullptr : found->second.get();
}

void registerBuiltinRuntimes() {
    if (!runtimes().empty()) {
        return;
    }
    registerRuntime(std::make_shared<CNativeKindRuntime>());
    registerRuntime(std::make_shared<CCppKindRuntime>());
    registerRuntime(std::make_shared<CPythonKindRuntime>());
    registerRuntime(std::make_shared<CLuaKindRuntime>());
}

} // namespace plugin_runtime
