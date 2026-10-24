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
#include "CHandler.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CPythonOverrides.h"
#include "core/CWrapper.h"
#include "object/CTile.h"

#include <algorithm>
#include <utility>
#include <unordered_set>

CObjectHandler::CObjectHandler() {}

struct CObjectHandler::RegistrationTransaction::State {
    std::shared_ptr<CObjectHandler> handler;
    std::function<bool()> canRollback;
    decltype(CObjectHandler::constructors) constructors;
    decltype(CObjectHandler::mapScopedTypes) mapScopedTypes;
    decltype(CObjectHandler::objectConfig) objectConfig;
    bool mapScriptScopeActive;
    bool nativeTileFactory;
    std::uint64_t previousEpoch;
    std::uint64_t epoch;
    bool committed = false;

    State(std::shared_ptr<CObjectHandler> handler, std::function<bool()> canRollback)
        : handler(std::move(handler)), canRollback(std::move(canRollback)), constructors(this->handler->constructors),
          mapScopedTypes(this->handler->mapScopedTypes), objectConfig(this->handler->objectConfig),
          mapScriptScopeActive(this->handler->mapScriptScopeActive),
          nativeTileFactory(this->handler->nativeTileFactory), previousEpoch(this->handler->registrationEpoch),
          epoch(++this->handler->nextRegistrationEpoch) {
        this->handler->registrationEpoch = epoch;
    }
};

CObjectHandler::RegistrationTransaction::RegistrationTransaction(std::shared_ptr<CObjectHandler> handler,
                                                                 std::function<bool()> canRollback) {
    if (!handler)
        throw std::invalid_argument("registration transaction requires an object handler");
    // Script factories may own py::object captures, including while their std::functions are copied.
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    state = std::make_unique<State>(std::move(handler), std::move(canRollback));
}

CObjectHandler::RegistrationTransaction::~RegistrationTransaction() {
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    bool restore = !state->committed && isCurrent();
    if (restore && state->canRollback) {
        try {
            restore = state->canRollback();
        } catch (...) {
            restore = false;
        }
    }
    if (restore) {
        auto &handler = *state->handler;
        handler.constructors.swap(state->constructors);
        handler.mapScopedTypes.swap(state->mapScopedTypes);
        handler.objectConfig.swap(state->objectConfig);
        handler.mapScriptScopeActive = state->mapScriptScopeActive;
        handler.nativeTileFactory = state->nativeTileFactory;
        handler.registrationEpoch = state->previousEpoch;
        // Cache generations cannot be reused after temporarily publishing different registrations.
        handler.navigationConfigRevision.fetch_add(1, std::memory_order_release);
    }
    state.reset(); // Release replaced or superseded Python factories before releasing the GIL.
}

bool CObjectHandler::RegistrationTransaction::isCurrent() const {
    return state->handler->registrationEpoch == state->epoch;
}

bool CObjectHandler::RegistrationTransaction::commit() {
    if (!isCurrent())
        return false;
    state->committed = true;
    std::optional<pybind11::gil_scoped_acquire> gil;
    if (Py_IsInitialized())
        gil.emplace();
    // Releasing displaced script factories can itself reenter the engine. Do it while ownership
    // can still be checked, before the caller publishes the restored map.
    state->constructors.clear();
    state->mapScopedTypes.clear();
    state->objectConfig.clear();
    return isCurrent();
}

void CObjectHandler::registerConfig(const std::string &path) {
    registerConfigDocument(path, CConfigurationProvider::getConfig(path));
}

void CObjectHandler::registerConfig(const std::string &path, CConfigurationProvider &provider) {
    registerConfigDocument(path, provider.getConfiguration(path));
}

void CObjectHandler::registerConfigDocument(const std::string &path, const std::shared_ptr<const json> &config) {
    if (!config) {
        vstd::logger::warning("Failed to load config:", path);
        return;
    }
    for (const auto &[key, value] : config->items()) {
        if (value.is_object() && !value.count("class") && !value.count("ref")) {
            continue;
        }
        objectConfig[key] = CJsonUtil::alias(config, value);
    }
    navigationConfigRevision.fetch_add(1, std::memory_order_release);
}

void CObjectHandler::registerConfig(const std::string &name, std::shared_ptr<json> value) {
    registerConfig(name, value ? std::make_shared<const json>(*value) : std::shared_ptr<const json>());
}

void CObjectHandler::registerConfig(const std::string &name, std::shared_ptr<const json> value) {
    objectConfig.insert_or_assign(name, std::move(value));
    navigationConfigRevision.fetch_add(1, std::memory_order_release);
}

void CObjectHandler::unregisterConfig(const std::string &name) {
    if (objectConfig.erase(name))
        navigationConfigRevision.fetch_add(1, std::memory_order_release);
}

std::uint64_t CObjectHandler::getNavigationConfigRevision() const {
    return navigationConfigRevision.load(std::memory_order_acquire);
}

std::optional<std::pair<bool, int>> CObjectHandler::getStaticTileNavigation(const std::string &type) {
    auto config = getConfig(type);
    if (!config && !constructors.contains(type))
        return std::pair(false, 1);
    if (!nativeTileFactory)
        return std::nullopt;
    if (!config || !config->is_object() || !config->contains("class") || !(*config)["class"].is_string() ||
        (*config)["class"].get<std::string>() != "CTile" || config->contains("ref") ||
        config->contains("effectReferences"))
        return std::nullopt;
    if (!config->contains("properties"))
        return std::pair(false, 1);
    const auto &properties = (*config)["properties"];
    if (!properties.is_object())
        return std::nullopt;
    const bool hasStep = properties.contains("canStep");
    const bool hasCost = properties.contains("movementCost");
    if ((hasStep && !properties["canStep"].is_boolean()) ||
        (hasCost && !properties["movementCost"].is_number_integer()))
        return std::nullopt;
    return std::pair(hasStep && properties["canStep"].get<bool>(),
                     hasCost ? std::max(1, properties["movementCost"].get<int>()) : 1);
}

void CObjectHandler::refreshTileRecipes() {
    const auto revision = getNavigationConfigRevision();
    if (tileRecipeRevision != revision) {
        if (!tileRecipes.empty())
            ++tileRecipeDiagnostics.invalidations;
        tileRecipes.clear();
        tileRecipeRevision = revision;
    }
}

void CObjectHandler::prepareTileRecipe(const std::shared_ptr<const json> &config) {
    refreshTileRecipes();
    if (!nativeTileFactory || !config || tileRecipes.contains(config.get()))
        return;
    if (!config->is_object() || config->size() != 2 || !config->contains("class") || !(*config)["class"].is_string() ||
        (*config)["class"].get<std::string>() != "CTile" || !config->contains("properties") ||
        !(*config)["properties"].is_object())
        return;
    auto recipe = std::make_shared<TileRecipe>();
    recipe->config = config;
    // Retain rejected documents as immutable owners too; a reused allocation must never inherit an old recipe.
    tileRecipes.emplace(config.get(), recipe);
    for (const auto &[key, value] : (*config)["properties"].items()) {
        if (key == "animation" || key == "label" || key == "description" || key == "tileType" || key == "name" ||
            key == "type" || key == "typeId") {
            if (!value.is_string())
                return;
            recipe->properties.push_back({key, value.get<std::string>()});
        } else if (key == "canStep") {
            if (!value.is_boolean())
                return;
            recipe->properties.push_back({key, value.get<bool>()});
        } else if (key == "movementCost" || key == "posx" || key == "posy" || key == "posz") {
            if (!value.is_number_integer())
                return;
            recipe->properties.push_back({key, value.get<int>()});
        } else {
            return;
        }
    }
    recipe->eligible = true;
    ++tileRecipeDiagnostics.compilations;
}

CObjectHandler::TileRecipeDiagnostics CObjectHandler::getTileRecipeDiagnostics() const { return tileRecipeDiagnostics; }

bool CObjectHandler::applyTileRecipe(const std::shared_ptr<CGameObject> &object, const json &config) {
    refreshTileRecipes();
    // Native registration alone does not authorize bypassing a plugin's derived metadata or setters.
    if (!nativeTileFactory || !object)
        return false;
    const bool native_wrapper = typeid(*object) == typeid(CWrapper<CTile>);
    if (typeid(*object) != typeid(CTile) && !native_wrapper)
        return false;
    if (native_wrapper && Py_IsInitialized()) {
        pybind11::gil_scoped_acquire gil;
        if (CPythonOverrides::find(object.get()))
            return false;
    }
    auto found = tileRecipes.find(&config);
    if (found == tileRecipes.end() || !found->second->eligible)
        return false;
    auto recipe = found->second;
    for (const auto &property : recipe->properties) {
        std::visit([&](const auto &value) { object->setProperty(property.key, value); }, property.value);
    }
    ++tileRecipeDiagnostics.applications;
    return true;
}

std::shared_ptr<const json> CObjectHandler::getConfig(const std::string &type) {
    auto found = objectConfig.find(type);
    return found == objectConfig.end() ? nullptr : found->second;
}

std::vector<std::string> CObjectHandler::getAllTypes() {
    std::vector<std::string> types;
    for (auto val : constructors | std::views::keys) {
        types.push_back(val);
    }
    for (auto val : objectConfig | std::views::keys) {
        types.push_back(val);
    }
    std::ranges::sort(types);
    auto duplicates = std::ranges::unique(types);
    types.erase(duplicates.begin(), duplicates.end());
    return types;
}

struct CObjectHandler::DefeatConstructionState {
    std::shared_ptr<DefeatConstructionState> parent;
    std::function<void()> requireCurrent;
    std::exception_ptr failure;

    void remember(std::exception_ptr primary) noexcept {
        if (parent) {
            parent->remember(primary);
        }
        if (!failure) {
            failure = std::move(primary);
        }
    }

    void rethrowFailure() const {
        if (parent) {
            parent->rethrowFailure();
        }
        if (failure) {
            std::rethrow_exception(failure);
        }
    }

    void currentWithoutLatching() const {
        if (parent) {
            parent->currentWithoutLatching();
        }
        if (failure) {
            std::rethrow_exception(failure);
        }
        if (requireCurrent) {
            requireCurrent();
        }
    }

    void check() {
        rethrowFailure();
        try {
            currentWithoutLatching();
        } catch (...) {
            remember(std::current_exception());
            rethrowFailure();
        }
    }

    void preserveIfStale(std::exception_ptr primary) {
        rethrowFailure();
        try {
            currentWithoutLatching();
        } catch (...) {
            remember(std::move(primary));
            rethrowFailure();
        }
    }
};

thread_local std::shared_ptr<CObjectHandler::DefeatConstructionState> CObjectHandler::defeatConstructionState;

CObjectHandler::DefeatConstructionScope::DefeatConstructionScope(std::function<void()> requireCurrent)
    : previous(defeatConstructionState), state(previous) {
    if (requireCurrent) {
        state = std::make_shared<DefeatConstructionState>();
        state->parent = previous;
        state->requireCurrent = std::move(requireCurrent);
    }
    if (state) {
        state->check();
    }
    defeatConstructionState = state;
}

CObjectHandler::DefeatConstructionScope::DefeatConstructionScope(DefeatConstructionScope &&other) noexcept
    : previous(std::move(other.previous)), state(std::move(other.state)), owned(std::exchange(other.owned, false)) {}

CObjectHandler::DefeatConstructionScope::~DefeatConstructionScope() noexcept {
    if (owned) {
        defeatConstructionState = std::move(previous);
    }
}

void CObjectHandler::DefeatConstructionScope::check() const {
    if (state) {
        state->check();
    }
}

void CObjectHandler::DefeatConstructionScope::rethrowFailure() const {
    if (state) {
        state->rethrowFailure();
    }
}

CObjectHandler::DefeatConstructionScope CObjectHandler::beginDefeatConstruction(std::function<void()> requireCurrent) {
    return DefeatConstructionScope(std::move(requireCurrent));
}

void CObjectHandler::checkDefeatConstruction() {
    if (auto state = defeatConstructionState) {
        state->check();
    }
}

void CObjectHandler::rethrowDefeatConstructionFailure() {
    if (auto state = defeatConstructionState) {
        state->rethrowFailure();
    }
}

void CObjectHandler::rememberDefeatConstructionFailure(std::exception_ptr primary) noexcept {
    if (auto state = defeatConstructionState) {
        state->remember(std::move(primary));
    }
}

void CObjectHandler::preserveDefeatConstructionCallbackFailure(std::exception_ptr primary) {
    if (auto state = defeatConstructionState) {
        state->preserveIfStale(std::move(primary));
    }
}

namespace game_detail {
void requireCurrentDefeatConstruction() { CObjectHandler::checkDefeatConstruction(); }

void preserveDefeatCallbackFailure(std::exception_ptr primary) {
    CObjectHandler::preserveDefeatConstructionCallbackFailure(std::move(primary));
}
} // namespace game_detail

std::shared_ptr<CGameObject> CObjectHandler::getType(const std::string &name) {
    auto construction = defeatConstructionState;
    if (construction) {
        construction->check();
    }
    try {
        if (vstd::ctn(constructors, name)) {
            auto object = constructors[name]();
            if (construction) {
                construction->check();
            }
            return object;
        }
        return std::shared_ptr<CGameObject>();
    } catch (...) {
        if (construction) {
            construction->remember(std::current_exception());
            construction->rethrowFailure();
        }
        throw;
    }
}

void CObjectHandler::registerType(std::string name, std::function<std::shared_ptr<CGameObject>()> constructor) {
    if (mapScriptScopeActive) {
        // A map script is registering this class. Several maps legitimately define the same class
        // name (e.g. StartEvent), and a map may be loaded while another map is still active during a
        // transition. Override an existing registration only when it too was owned by a map script,
        // so the destination map runs its own class instead of the previously loaded map's -- e.g.
        // entering the ritual map after Nouraajd must build ritualStart from the ritual StartEvent,
        // not Nouraajd's. Persistent registrations (core types, native/global plugins, or explicit
        // manual registerType overrides made outside a map scope) are left untouched.
        const bool alreadyPersistent = constructors.contains(name) && !mapScopedTypes.contains(name);
        if (alreadyPersistent) {
            return;
        }
        if (name == "CTile")
            nativeTileFactory = false;
        constructors.insert_or_assign(name, std::move(constructor));
        navigationConfigRevision.fetch_add(1, std::memory_order_release);
        mapScopedTypes.insert(std::move(name));
        return;
    }
    // Persistent registration path: keep first-registration-wins so core types (registered first at
    // game init) and explicit test/manual overrides cannot be clobbered by later registrations.
    if (constructors.insert(std::make_pair(std::move(name), std::move(constructor))).second)
        navigationConfigRevision.fetch_add(1, std::memory_order_release);
}

void CObjectHandler::registerNativeType(std::string name, std::function<std::shared_ptr<CGameObject>()> constructor) {
    const bool trustedTile = name == "CTile" && !constructors.contains(name);
    registerType(std::move(name), std::move(constructor));
    if (trustedTile)
        nativeTileFactory = true;
}

void CObjectHandler::beginMapScriptScope() { mapScriptScopeActive = true; }

void CObjectHandler::endMapScriptScope() { mapScriptScopeActive = false; }

// TODO: add option to provide custom configuration from string
std::shared_ptr<CGameObject> CObjectHandler::_createObject(std::shared_ptr<CGame> game, const std::string &type) {
    CSerializationReadContext context(false, type);
    return _createObject(std::move(game), type, context);
}

std::shared_ptr<CGameObject> CObjectHandler::_createObject(std::shared_ptr<CGame> game, const std::string &type,
                                                           CSerializationReadContext &context) {
    auto config = getConfig(type);
    if (!config) {
        vstd::logger::debug("No config found for:", type, "falling back to class-name construction");
        config = std::make_shared<const json>(json{{"class", type}});
    }
    prepareTileRecipe(config);
    context.keepDocument(config);
    auto object = serializationValueOrThrow(
        CSerialization::deserializeExpected<std::shared_ptr<CGameObject>>(game, *config, context));
    if (!object) {
        return object;
    }
    object->setTypeId(type);
    return object;
}

std::shared_ptr<CGameObject> CObjectHandler::_clone(const std::shared_ptr<CGameObject> &object) {
    auto shared_ptr = CSerialization::cloneObject(object);
    if (!shared_ptr) {
        return nullptr;
    }
    shared_ptr->setName(CSerialization::generateName(shared_ptr));
    return shared_ptr;
}

std::vector<std::string> CObjectHandler::getAllSubTypes(const std::string &claz) {
    std::vector<std::string> ret;
    for (const auto &type : getAllTypes()) {
        auto prototype = getType(getClass(type));
        if (prototype && prototype->meta()->inherits(claz)) {
            ret.push_back(type);
        }
    }
    return ret;
}

std::vector<std::string> CObjectHandler::getDefeatSubTypes(const std::string &claz,
                                                           const std::function<void()> &requireCurrent) {
    std::vector<std::string> ret;
    for (const auto &type : getAllTypes()) {
        if (requireCurrent) {
            requireCurrent();
        }
        auto prototype = getType(getClass(type));
        if (requireCurrent) {
            requireCurrent();
        }

        if (prototype && prototype->meta()->inherits(claz)) {
            ret.push_back(type);
        }
    }
    return ret;
}

std::string CObjectHandler::getClass(const std::string &type) {
    std::unordered_set<std::string> visited;
    auto current = type;
    while (visited.insert(current).second) {
        auto conf = getConfig(current);
        if (CJsonUtil::isRef(conf)) {
            current = (*conf)["ref"].get<std::string>();
            continue;
        }
        if (conf && conf->is_object() && conf->contains("class") && (*conf)["class"].is_string()) {
            return (*conf)["class"].get<std::string>();
        }
        return "";
    }
    return "";
}
void CObjectHandler::registerConfig(const std::set<std::string> &paths) {
    for (const auto &path : paths) {
        registerConfig(path);
    }
}

void CObjectHandler::registerConfig(const std::set<std::string> &paths, CConfigurationProvider &provider) {
    for (const auto &path : paths) {
        registerConfig(path, provider);
    }
}
