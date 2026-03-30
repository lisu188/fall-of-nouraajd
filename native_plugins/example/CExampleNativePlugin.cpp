/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2025  Andrzej Lis

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
#include "core/CNativePlugin.h"
#include "object/CGameObject.h"

class CExampleNativePluginMarker : public CGameObject {
  V_META(CExampleNativePluginMarker, CGameObject, vstd::meta::empty())
public:
  CExampleNativePluginMarker() {
    setLabel("Native Plugin Marker");
    setDescription("A proof object registered by the example native plugin.");
    setTags(std::set<std::string>{"example", "native", "plugin"});
  }
};

class CExampleNativePlugin : public CNativePlugin {
public:
  static CNativePluginInfo static_info() {
    return {"example_native_plugin", "1.0.0",
            "Registers a simple native marker object for regression tests."};
  }

  CNativePluginInfo info() const override { return static_info(); }

  void registerContent(CNativePluginContext &context) override {
    context.registerType(
        CExampleNativePluginMarker::static_meta()->name(),
        []() -> std::shared_ptr<CGameObject> {
          return std::make_shared<CExampleNativePluginMarker>();
        });
    auto config = std::make_shared<json>();
    (*config)["class"] = CExampleNativePluginMarker::static_meta()->name();
    (*config)["properties"]["label"] = "Native Plugin Marker";
    (*config)["properties"]["description"] =
        "A proof object registered by the example native plugin.";
    (*config)["properties"]["tags"] = {"example", "native", "plugin"};
    context.registerConfig("exampleNativePluginMarker", config);
  }
};

REGISTER_NATIVE_PLUGIN(CExampleNativePlugin)
