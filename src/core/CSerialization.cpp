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
#include <mutex>
#include "core/CSerialization.h"
#include "core/CSaveFormat.h"
#include "core/CGame.h"
#include "core/CJsonUtil.h"
#include "core/CList.h"
#include "core/CMap.h"
#include "core/CTypes.h"
#include "object/CCreature.h"
#include "object/CEffect.h"

#include <atomic>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <vector>

std::shared_ptr<const CSerializerBase> CSerialization::serializer(std::type_index type) {
    return CTypes::findCodec(type);
}

std::shared_ptr<json> object_serialize(const std::shared_ptr<CGameObject> &, CSerializationWriteContext &);
std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &, const json *,
                                                CSerializationReadContext &);
std::shared_ptr<json> array_serialize(const std::set<std::shared_ptr<CGameObject>> &, CSerializationWriteContext &);
std::set<std::shared_ptr<CGameObject>> array_deserialize(const std::shared_ptr<CGame> &, const json *,
                                                         CSerializationReadContext &);
std::shared_ptr<json> map_serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &,
                                    CSerializationWriteContext &);
std::map<std::string, std::shared_ptr<CGameObject>> map_deserialize(const std::shared_ptr<CGame> &, const json *,
                                                                    CSerializationReadContext &);

namespace {
struct NameGenerationState {
    std::optional<std::uint32_t> fixtureSeed;
    std::uint64_t fixtureSequence = 0;
    bool startupSeeded = false;
    bool sessionStarted = false;
};

NameGenerationState &nameGenerationState() {
    static NameGenerationState state;
    return state;
}

std::mutex &nameGenerationMutex() {
    static std::mutex mutex;
    return mutex;
}

std::atomic<bool> &fixtureNamesEnabled() {
    static std::atomic<bool> enabled{false};
    return enabled;
}

std::atomic<std::uint64_t> &productionNameSequence() {
    static std::atomic<std::uint64_t> sequence{0};
    return sequence;
}

constexpr const char *graphEnvelopeKey = "$gameGraphEnvelope";

// Only effect actor links are references. Other reflected properties retain the existing tree encoding.
class EffectWriteContext {
  public:
    explicit EffectWriteContext(bool includeDetached = true) : includeDetached(includeDetached) {}

    int actorId(const std::shared_ptr<CCreature> &actor) {
        if (!actor) {
            return 0;
        }
        auto found = actorIds.find(actor.get());
        if (found != actorIds.end()) {
            return found->second;
        }
        if (actors.size() >= static_cast<std::size_t>(std::numeric_limits<int>::max())) {
            throw std::runtime_error("Too many effect actors to serialize");
        }
        const int id = static_cast<int>(actors.size()) + 1;
        actorIds.emplace(actor.get(), id);
        actors.push_back({actor, false, false});
        return id;
    }

    bool writeRecord(const std::shared_ptr<CGameObject> &object, const std::shared_ptr<json> &config) {
        if (auto actor = std::dynamic_pointer_cast<CCreature>(object)) {
            const int id = actorId(actor);
            auto &entry = actors[id - 1];
            if (entry.defined) {
                if (!entry.completed) {
                    throw std::runtime_error("Cannot serialize cyclic creature ownership through ordinary properties");
                }
                (*config)["effectActorReference"] = id;
                return false;
            }
            entry.defined = true;
            (*config)["effectActorId"] = id;
        }
        if (auto effect = std::dynamic_pointer_cast<CEffect>(object)) {
            const int caster = actorId(effect->getCaster());
            const int victim = actorId(effect->getVictim());
            if (caster || victim) {
                (*config)["effectReferences"] = {
                    {"caster", caster ? json(caster) : json(nullptr)},
                    {"victim", victim ? json(victim) : json(nullptr)},
                };
            }
        }
        return true;
    }

    void complete(const std::shared_ptr<CGameObject> &object) {
        if (auto actor = std::dynamic_pointer_cast<CCreature>(object)) {
            actors[actorIds.at(actor.get()) - 1].completed = true;
        }
    }

    void finish(json &root, CSerializationWriteContext &context) {
        auto detached = json::array();
        if (includeDetached) {
            // Serializing a detached actor can discover further actors; the growing queue visits each once.
            for (std::size_t index = 0; index < actors.size(); ++index) {
                if (!actors[index].defined) {
                    auto actor = actors[index].actor;
                    detached[detached.size()] = *object_serialize(actor, context);
                }
            }
        }
        if (!actors.empty()) {
            json graph = json::object();
            graph["version"] = 1;
            graph["actors"] = std::move(detached);
            if (root.is_object()) {
                if (root.contains("effectGraph")) {
                    throw CSerializationException({CSerializationErrorCode::InvalidInput, context.source(),
                                                   context.path(), context.objectType(),
                                                   "Custom codec output collides with the reserved effectGraph field"});
                }
                root["effectGraph"] = std::move(graph);
            } else {
                json envelope = json::object();
                envelope["version"] = 1;
                envelope["value"] = std::move(root);
                root = json::object();
                root[graphEnvelopeKey] = std::move(envelope);
                root["effectGraph"] = std::move(graph);
                if (auto error = CSaveFormat::validateDocumentStructure(root)) {
                    throw CSerializationException({CSerializationErrorCode::InvalidInput, context.source(),
                                                   context.path(), context.objectType(), *error});
                }
            }
        }
    }

    std::unordered_map<int, std::shared_ptr<CCreature>> externalActors() const {
        std::unordered_map<int, std::shared_ptr<CCreature>> result;
        for (std::size_t index = 0; index < actors.size(); ++index) {
            if (!actors[index].defined) {
                result.emplace(static_cast<int>(index) + 1, actors[index].actor);
            }
        }
        return result;
    }

  private:
    struct Actor {
        std::shared_ptr<CCreature> actor;
        bool defined;
        bool completed;
    };
    bool includeDetached;
    std::unordered_map<const CCreature *, int> actorIds;
    std::vector<Actor> actors;
};

class EffectReadContext {
  public:
    explicit EffectReadContext(CSerializationReadContext &context,
                               std::unordered_map<int, std::shared_ptr<CCreature>> external = {})
        : context(context), actors(std::move(external)) {}

    [[noreturn]] void fail(const std::string &message) {
        if (!failure)
            failure = CSerializationError{CSerializationErrorCode::MalformedGraph, context.source(), context.path(),
                                          context.objectType(), "Invalid effect graph: " + message};
        throw CSerializationException(*failure);
    }

    int readId(const json &value) {
        if (!value.is_number_integer()) {
            fail("actor id must be a positive integer");
        }
        const auto id = value.get<unsigned long long>();
        if (id == 0 || id > static_cast<unsigned long long>(std::numeric_limits<int>::max())) {
            fail("actor id must be a positive integer");
        }
        return static_cast<int>(id);
    }

    bool hasGraph() const noexcept { return graph != nullptr; }

    void prepare(const std::shared_ptr<CGame> &game, const json *config) {
        if (!config || !config->is_object() || !config->contains("effectGraph")) {
            return;
        }
        if (graph) {
            if (graphRoot != config) {
                fail("nested effect graph");
            }
            return;
        }
        auto &value = (*config)["effectGraph"];
        if (!value.is_object() || !value.contains("version") || !value["version"].is_number_integer() ||
            value["version"].get<unsigned long long>() != 1 || !value.contains("actors") ||
            !value["actors"].is_array()) {
            fail("unsupported graph version or missing actor table");
        }
        graphRoot = config;
        graph = &value;

        // Allocate actor identities before setting properties: a forward alias can precede its definition in JSON.
        std::vector<const json *> pending{config};
        while (!pending.empty()) {
            auto *node = pending.back();
            pending.pop_back();
            if (node->is_object()) {
                needsFixup = needsFixup || node->contains("effectReferences");
                if (node->contains("effectActorId") && (node->contains("class") || node->contains("ref"))) {
                    const int id = readId((*node)["effectActorId"]);
                    if (actors.contains(id) || node->contains("effectActorReference")) {
                        fail("duplicate actor definition");
                    }
                    if (!node->contains("class") || !(*node)["class"].is_string()) {
                        fail("actor definition must name a class");
                    }
                    const auto type = (*node)["class"].get<std::string>();
                    auto actor = std::dynamic_pointer_cast<CCreature>(game->getObjectHandler()->getType(type));
                    if (!actor) {
                        fail("actor definition does not construct a creature: " + type);
                    }
                    actor->setGame(game);
                    actors.emplace(id, std::move(actor));
                    definitions.emplace(id, node);
                }
                for (auto &child : node->items()) {
                    pending.push_back(&child.second);
                }
            } else if (node->is_array()) {
                for (auto &child : *node) {
                    pending.push_back(&child);
                }
            }
        }
    }

    std::shared_ptr<CCreature> definition(const json *config) {
        if (!config->contains("effectActorId")) {
            return nullptr;
        }
        const int id = readId((*config)["effectActorId"]);
        if (!graph || !definitions.contains(id) || definitions.at(id) != config) {
            fail("actor definition is outside its snapshot graph");
        }
        loadedDefinitions.insert(id);
        return actors.at(id);
    }

    bool alreadyLoading(const json *config) {
        return config->contains("effectActorId") && loadedDefinitions.contains(readId((*config)["effectActorId"]));
    }

    std::shared_ptr<CCreature> reference(const std::shared_ptr<CGame> &game, const json *config,
                                         CSerializationReadContext &context) {
        const int id = readId((*config)["effectActorReference"]);
        if (!graph || !actors.contains(id) || config->size() != 2 || !config->contains("class") ||
            !(*config)["class"].is_string()) {
            fail("dangling or malformed actor alias");
        }
        if (definitions.contains(id) && !loadedDefinitions.contains(id)) {
            // CMap indexes actors as soon as its objects setter runs; populate a forward alias before returning it.
            object_deserialize(game, definitions.at(id), context);
        }
        if (definitions.contains(id) && !completedDefinitions.contains(id)) {
            fail("cyclic creature ownership through ordinary properties");
        }
        const auto actor = actors.at(id);
        const auto type = actor->getType().empty() ? actor->meta()->name() : actor->getType();
        if ((*config)["class"].get<std::string>() != type) {
            fail("actor alias class does not match its definition");
        }
        return actors.at(id);
    }

    void readRecord(const std::shared_ptr<CGameObject> &object, const json *config) {
        if (!config->contains("effectReferences")) {
            return;
        }
        const auto effect = std::dynamic_pointer_cast<CEffect>(object);
        const auto &links = (*config)["effectReferences"];
        if (!graph || !effect || !links.is_object() || !links.contains("caster") || !links.contains("victim")) {
            fail("effect references require an effect and a snapshot graph");
        }
        effects.push_back({effect, links["caster"].is_null() ? 0 : readId(links["caster"]),
                           links["victim"].is_null() ? 0 : readId(links["victim"])});
    }

    void initialize(const std::shared_ptr<CGameObject> &object) {
        if (!object || !object->meta()->has_method("initialize", object)) {
            return;
        }
        if (graph && needsFixup) {
            if (initializationSet.insert(object.get()).second) {
                initializations.push_back(object);
            }
        } else {
            object->meta()->invoke_method<void>("initialize", object);
        }
    }

    void complete(const json *config) {
        if (config->contains("effectActorId")) {
            completedDefinitions.insert(readId((*config)["effectActorId"]));
        }
    }

    void finish(const std::shared_ptr<CGame> &game, CSerializationReadContext &context) {
        if (failure)
            throw CSerializationException(*failure);
        if (graph) {
            for (auto &record : (*graph)["actors"]) {
                if (!record.is_object() || !record.contains("effectActorId")) {
                    fail("detached actor table contains a non-definition");
                }
                if (!object_deserialize(game, &record, context)) {
                    fail("detached actor could not be loaded");
                }
            }
        }
        if (failure) {
            throw CSerializationException(*failure);
        }
        if (completedDefinitions.size() != definitions.size()) {
            fail("actor definition was not loaded");
        }
        for (const auto &entry : effects) {
            if ((entry.caster && !actors.contains(entry.caster)) || (entry.victim && !actors.contains(entry.victim))) {
                fail("dangling effect actor reference");
            }
        }
        // Validate all links before creating the existing strong actor/effect ownership relationships.
        for (const auto &entry : effects) {
            entry.effect->setCaster(entry.caster ? actors.at(entry.caster) : nullptr);
            entry.effect->setVictim(entry.victim ? actors.at(entry.victim) : nullptr);
        }
        for (std::size_t index = 0; index < initializations.size(); ++index) {
            auto object = initializations[index];
            object->meta()->invoke_method<void>("initialize", object);
        }
    }

  private:
    struct EffectLinks {
        std::shared_ptr<CEffect> effect;
        int caster;
        int victim;
    };
    CSerializationReadContext &context;
    const json *graphRoot = nullptr;
    const json *graph = nullptr;
    bool needsFixup = false;
    std::optional<CSerializationError> failure;
    std::unordered_map<int, std::shared_ptr<CCreature>> actors;
    std::unordered_map<int, const json *> definitions;
    std::unordered_set<int> loadedDefinitions;
    std::unordered_set<int> completedDefinitions;
    std::vector<EffectLinks> effects;
    std::vector<std::shared_ptr<CGameObject>> initializations;
    std::unordered_set<const CGameObject *> initializationSet;
};

} // namespace

class CSerializationWriteContext::State {
  public:
    explicit State(bool includeDetached) : effects(includeDetached) {}
    EffectWriteContext effects;
    std::size_t objectDepth = 0;
};

class CSerializationReadContext::State {
  public:
    State(CSerializationReadContext &context, const std::unordered_map<int, std::shared_ptr<CCreature>> &external)
        : effects(context, external) {}
    EffectReadContext effects;
    std::size_t objectDepth = 0;
};

CSerializationWriteContext::CSerializationWriteContext(std::string source, bool includeDetached)
    : sourceName(std::move(source)), includeDetached(includeDetached) {}
CSerializationWriteContext::~CSerializationWriteContext() = default;
bool CSerializationWriteContext::begin() {
    if (depth == 0)
        operationState.reset();
    return depth++ == 0;
}
void CSerializationWriteContext::end() noexcept { --depth; }
CSerializationWriteContext::State &CSerializationWriteContext::state() {
    if (!operationState)
        operationState = std::make_unique<State>(includeDetached);
    return *operationState;
}
void CSerializationWriteContext::finish(json &document) {
    if (document.is_object()) {
        for (const auto *key : {graphEnvelopeKey, "effectGraph"}) {
            if (document.contains(key)) {
                throw CSerializationException(
                    {CSerializationErrorCode::InvalidInput, sourceName, propertyPath, typeName,
                     "Custom codec output uses the reserved graph metadata field '" + std::string(key) + "'"});
            }
        }
    }
    if (operationState)
        operationState->effects.finish(document, *this);
}
std::unordered_map<int, std::shared_ptr<CCreature>> CSerializationWriteContext::externalActors() {
    return state().effects.externalActors();
}

CSerializationWriteContext::PropertyScope::PropertyScope(CSerializationWriteContext &context, std::string property,
                                                         std::string type)
    : context(context), previousPath(context.propertyPath), previousType(context.typeName) {
    if (!property.empty())
        context.propertyPath += (context.propertyPath.empty() ? "" : ".") + property;
    if (!type.empty())
        context.typeName = std::move(type);
}
CSerializationWriteContext::PropertyScope::~PropertyScope() {
    context.propertyPath = std::move(previousPath);
    context.typeName = std::move(previousType);
}

CSerializationReadContext::CSerializationReadContext(bool strict, std::string source,
                                                     std::unordered_map<int, std::shared_ptr<CCreature>> external)
    : strictPolicy(strict), sourceName(std::move(source)), external(std::move(external)) {}
CSerializationReadContext::~CSerializationReadContext() = default;
bool CSerializationReadContext::begin() {
    if (depth == 0) {
        operationState.reset();
        documents.clear();
    }
    return depth++ == 0;
}
void CSerializationReadContext::end() noexcept { --depth; }
CSerializationReadContext::State &CSerializationReadContext::state() {
    if (!operationState)
        operationState = std::make_unique<State>(*this, external);
    return *operationState;
}
const json &CSerializationReadContext::prepare(const std::shared_ptr<CGame> &game, const json &document) {
    const json *payload = &document;
    if (document.is_object() && document.contains(graphEnvelopeKey)) {
        const auto &envelope = document.at(graphEnvelopeKey);
        if (document.size() != 2 || !document.contains("effectGraph") || !envelope.is_object() ||
            envelope.size() != 2 || !envelope.contains("version") || !envelope.at("version").is_number_integer() ||
            envelope.at("version").get<unsigned long long>() != 1 || !envelope.contains("value") ||
            envelope.at("value").is_object()) {
            state().effects.fail("malformed or unsupported non-object graph envelope");
        }
        if (auto error = CSaveFormat::validateDocumentStructure(document)) {
            state().effects.fail(*error);
        }
        payload = &envelope.at("value");
    }
    if (document.is_object() && document.contains("effectGraph")) {
        if (!game)
            throw CSerializationException({CSerializationErrorCode::InvalidInput, sourceName, propertyPath, typeName,
                                           "An effect graph requires a game"});
        state().effects.prepare(game, &document);
    }
    return *payload;
}
void CSerializationReadContext::finish(const std::shared_ptr<CGame> &game) {
    if (operationState)
        operationState->effects.finish(game, *this);
}
void CSerializationReadContext::keepDocument(std::shared_ptr<const json> document) {
    if (document)
        documents.push_back(std::move(document));
}

CSerializationReadContext::PropertyScope::PropertyScope(CSerializationReadContext &context, std::string property,
                                                        std::string type, bool index)
    : context(context), previousPath(context.propertyPath), previousProperty(context.propertyName),
      previousType(context.typeName) {
    context.propertyPath += (context.propertyPath.empty() || index ? "" : ".") + property;
    if (!index)
        context.propertyName = std::move(property);
    if (!type.empty())
        context.typeName = std::move(type);
}
CSerializationReadContext::PropertyScope::~PropertyScope() {
    context.propertyPath = std::move(previousPath);
    context.propertyName = std::move(previousProperty);
    context.typeName = std::move(previousType);
}

namespace {
class ObjectDepthScope {
  public:
    explicit ObjectDepthScope(std::size_t &depth) : depth(depth) { ++depth; }
    ~ObjectDepthScope() { --depth; }

  private:
    std::size_t &depth;
};

bool shouldSkipInvalidArrayEntryInStrictMode(const CSerializationReadContext &context) {
    return context.property() == "quests" || context.property() == "completedQuests";
}

std::shared_ptr<json> primitiveValuesConfig(const std::shared_ptr<CGameObject> &object,
                                            CSerializationWriteContext &context) {
    if (!object || !CTypes::isPrimitiveType(std::type_index(typeid(*object))) ||
        !object->meta()->has_property("values", object)) {
        return nullptr;
    }

    auto values = std::make_shared<json>();
    CSerialization::setProperty(values, "values", object->getProperty<std::any>("values"), context);
    if (!values->contains("values")) {
        return nullptr;
    }
    return CJsonUtil::clone(&(*values)["values"]);
}

template <typename T> bool isPrimitiveMapWrapper() {
    const auto type = std::type_index(typeid(T));
    return type == std::type_index(typeid(CMapStringString)) || type == std::type_index(typeid(CMapStringInt)) ||
           type == std::type_index(typeid(CMapIntString)) || type == std::type_index(typeid(CMapIntInt));
}

template <typename T> bool isCompatiblePrimitiveObjectConfig(const std::shared_ptr<CGame> &game, const json *value) {
    std::string class_name;
    if (CJsonUtil::isRef(value)) {
        if (!game || !game->getObjectHandler()) {
            return false;
        }
        class_name = game->getObjectHandler()->getClass((*value)["ref"].get<std::string>());
    } else if (CJsonUtil::isType(value)) {
        class_name = (*value)["class"].get<std::string>();
    }
    if (class_name.empty()) {
        return false;
    }
    auto type = game && game->getObjectHandler() ? game->getObjectHandler()->getType(class_name) : nullptr;
    return type && type->meta()->inherits(T::static_meta()->name());
}

template <typename T> bool shouldKeepPrimitiveObjectConfig(const std::shared_ptr<CGame> &game, const json *value) {
    if (!CJsonUtil::isObject(value)) {
        return false;
    }
    return !isPrimitiveMapWrapper<T>() || value->contains("properties") ||
           isCompatiblePrimitiveObjectConfig<T>(game, value);
}

template <typename T>
std::shared_ptr<json> primitiveObjectConfig(const std::shared_ptr<CGame> &game, std::type_index property,
                                            const json *value) {
    if (property != std::type_index(typeid(std::shared_ptr<T>)) || !CTypes::isPrimitiveType<T>() ||
        shouldKeepPrimitiveObjectConfig<T>(game, value)) {
        return nullptr;
    }

    auto config = std::make_shared<json>();
    (*config)["class"] = T::static_meta()->name();
    (*config)["properties"]["values"] = *value;
    return config;
}

std::shared_ptr<json> primitiveObjectConfig(const std::shared_ptr<CGame> &game, std::type_index property,
                                            const json *value) {
    if (auto config = primitiveObjectConfig<CListString>(game, property, value)) {
        return config;
    }
    if (auto config = primitiveObjectConfig<CListInt>(game, property, value)) {
        return config;
    }
    if (auto config = primitiveObjectConfig<CMapStringString>(game, property, value)) {
        return config;
    }
    if (auto config = primitiveObjectConfig<CMapStringInt>(game, property, value)) {
        return config;
    }
    if (auto config = primitiveObjectConfig<CMapIntString>(game, property, value)) {
        return config;
    }
    return primitiveObjectConfig<CMapIntInt>(game, property, value);
}

// The registered primitive wrappers (CList*/CMap*) all expose their value through a "values"
// collection (a std::set or std::map). A flattened primitive therefore always deserializes from a
// JSON array or object; a bare scalar can never be a valid flattened form for such a property.
bool isPrimitiveCollectionValueType(std::type_index valueType) {
    return valueType != std::type_index(typeid(int)) && valueType != std::type_index(typeid(std::string)) &&
           valueType != std::type_index(typeid(bool));
}

template <typename T> bool isPrimitiveCollectionPointer(std::type_index property) {
    if (property != std::type_index(typeid(std::shared_ptr<T>)) || !CTypes::isPrimitiveType<T>()) {
        return false;
    }
    auto valueType = CTypes::primitiveValueType<T>();
    return valueType && isPrimitiveCollectionValueType(*valueType);
}

bool isPrimitiveCollectionPointer(std::type_index property) {
    return isPrimitiveCollectionPointer<CListString>(property) || isPrimitiveCollectionPointer<CListInt>(property) ||
           isPrimitiveCollectionPointer<CMapStringString>(property) ||
           isPrimitiveCollectionPointer<CMapStringInt>(property) ||
           isPrimitiveCollectionPointer<CMapIntString>(property) || isPrimitiveCollectionPointer<CMapIntInt>(property);
}

// Guards scalar-to-collection coercion for primitive-wrapper properties. Returns true when the
// scalar has been handled (rejected) and the caller must not attempt the underlying scalar
// assignment. In strict mode an incompatible scalar raises a specific error; otherwise it is
// skipped so the property keeps its default value instead of being silently mis-typed.
bool rejectScalarForPrimitiveCollection(std::type_index property, const std::string &key,
                                        CSerializationReadContext &context) {
    if (!isPrimitiveCollectionPointer(property)) {
        return false;
    }
    const std::string message = "Cannot deserialize scalar value for property '" + key +
                                "' which expects a primitive collection wrapper (a JSON array or object is required)";
    if (context.isStrict()) {
        throw CSerializationException(
            {CSerializationErrorCode::InvalidInput, context.source(), context.path(), context.objectType(), message});
    }
    vstd::logger::warning(message);
    return true;
}

class CGameObjectPointerSerializer : public CSerializerBase {
  public:
    CSerializationResult<json> serialize(const std::any &object, CSerializationWriteContext &context) const final {
        return serializationResult([&]() -> json {
            auto encoded = object_serialize(vstd::any_cast<std::shared_ptr<CGameObject>>(object), context);
            return std::move(*encoded);
        });
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &object,
                                               CSerializationReadContext &context) const final {
        return serializationResult([&]() -> std::any { return object_deserialize(game, &object, context); });
    }
};

class CGameObjectSetSerializer : public CSerializerBase {
  public:
    CSerializationResult<json> serialize(const std::any &object, CSerializationWriteContext &context) const final {
        return serializationResult([&]() -> json {
            auto encoded = array_serialize(vstd::any_cast<std::set<std::shared_ptr<CGameObject>>>(object), context);
            return std::move(*encoded);
        });
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &object,
                                               CSerializationReadContext &context) const final {
        return serializationResult([&]() -> std::any { return array_deserialize(game, &object, context); });
    }
};

class CGameObjectMapSerializer : public CSerializerBase {
  public:
    CSerializationResult<json> serialize(const std::any &object, CSerializationWriteContext &context) const final {
        return serializationResult([&]() -> json {
            auto encoded =
                map_serialize(vstd::any_cast<std::map<std::string, std::shared_ptr<CGameObject>>>(object), context);
            return std::move(*encoded);
        });
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &object,
                                               CSerializationReadContext &context) const final {
        return serializationResult([&]() -> std::any { return map_deserialize(game, &object, context); });
    }
};

} // namespace

std::shared_ptr<CSerializerBase> game_object_pointer_serializer() {
    static auto serializer = std::make_shared<CGameObjectPointerSerializer>();
    return serializer;
}

std::shared_ptr<CSerializerBase> game_object_set_serializer() {
    static auto serializer = std::make_shared<CGameObjectSetSerializer>();
    return serializer;
}

std::shared_ptr<CSerializerBase> game_object_map_serializer() {
    static auto serializer = std::make_shared<CGameObjectMapSerializer>();
    return serializer;
}

void CSerialization::setProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                 const std::shared_ptr<json> &value) {
    if (!object || !value)
        return;
    CSerializationReadContext context;
    setProperty(object, key, *value, context);
}

void CSerialization::setProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                 const json &document, CSerializationReadContext &context) {
    if (!object)
        return;
    CSerializationOperation operation(context);
    const auto &value = operation.isRoot() ? context.prepare(object->getGame(), document) : document;
    CSerializationReadContext::PropertyScope propertyScope(context, key, object->meta()->name());
    if (value.is_boolean()) {
        setBooleanProperty(object, key, value.get<bool>(), context);
    } else if (value.is_number()) {
        setNumericProperty(object, key, value.get<int>(), context);
    } else if (value.is_string()) {
        setStringProperty(object, key, value.get<std::string>(), context);
    } else if (value.is_array()) {
        setArrayProperty(object, getProperty(object, key), key, value, context);
    } else if (value.is_object()) {
        setObjectProperty(object, getProperty(object, key), key, value, context);
    }
    if (operation.isRoot())
        context.finish(object->getGame());
}

std::type_index CSerialization::getProperty(const std::shared_ptr<CGameObject> &object, const std::string &name) {
    return object->meta()->get_property_type(object, name);
}

void CSerialization::setArrayProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                      const std::string &key, const json &value, CSerializationReadContext &context) {
    if (auto config = primitiveObjectConfig(object->getGame(), property, &value)) {
        context.keepDocument(config);
        setOtherProperty(property, object, key, *config, context);
        return;
    }
    setOtherProperty(property != V_VOID ? property : std::type_index(typeid(std::set<std::shared_ptr<CGameObject>>)),
                     object, key, value, context);
}

void CSerialization::setObjectProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                       const std::string &key, const json &value, CSerializationReadContext &context) {
    if (auto config = primitiveObjectConfig(object->getGame(), property, &value)) {
        context.keepDocument(config);
        setOtherProperty(property, object, key, *config, context);
        return;
    }
    setOtherProperty(property != V_VOID ? property : getGenericPropertyType(&value), object, key, value, context);
}

void CSerialization::setNumericProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, int value,
                                        CSerializationReadContext &context) {
    const auto property = getProperty(object, key);
    if (property == std::type_index(typeid(std::string)))
        object->setStringProperty(key, vstd::str(value));
    else if (!rejectScalarForPrimitiveCollection(property, key, context))
        object->setNumericProperty(key, value);
}

void CSerialization::setBooleanProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, bool value,
                                        CSerializationReadContext &context) {
    const auto property = getProperty(object, key);
    if (property == std::type_index(typeid(std::string)))
        object->setStringProperty(key, vstd::str(value));
    else if (!rejectScalarForPrimitiveCollection(property, key, context))
        object->setBoolProperty(key, value);
}

void CSerialization::setStringProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                       const std::string &value, CSerializationReadContext &context) {
    const auto property = getProperty(object, key);
    auto coerced = coerceStringProperty(property, value);
    if (std::holds_alternative<std::string>(coerced)) {
        if (!rejectScalarForPrimitiveCollection(property, key, context))
            object->setStringProperty(key, std::get<std::string>(coerced));
    } else if (std::holds_alternative<int>(coerced)) {
        setNumericProperty(object, key, std::get<int>(coerced), context);
    } else if (std::holds_alternative<bool>(coerced)) {
        setBooleanProperty(object, key, std::get<bool>(coerced), context);
    } else if (std::holds_alternative<std::shared_ptr<json>>(coerced)) {
        auto document = std::get<std::shared_ptr<json>>(coerced);
        context.keepDocument(document);
        if (document->is_array()) {
            setArrayProperty(object, getProperty(object, key), key, *document, context);
        } else if (document->is_object()) {
            setObjectProperty(object, getProperty(object, key), key, *document, context);
        } else if (document->is_boolean()) {
            setBooleanProperty(object, key, document->get<bool>(), context);
        } else if (document->is_number()) {
            setNumericProperty(object, key, document->get<int>(), context);
        }
    }
}

bool CSerialization::isString(const std::shared_ptr<CGameObject> &object, const std::string &key) {
    return getProperty(object, key) == std::type_index(typeid(std::string));
}

void CSerialization::setOtherProperty(std::type_index deserializedId, const std::shared_ptr<CGameObject> &object,
                                      const std::string &key, const json &value, CSerializationReadContext &context) {
    auto codec = CTypes::findCodec(deserializedId);
    if (!codec) {
        throw CSerializationException({CSerializationErrorCode::MissingCodec, context.source(), context.path(),
                                       object->meta()->name(), "No JSON codec registered for property '" + key + "'"});
    }
    std::any result;
    try {
        const auto &payload = context.prepare(object->getGame(), value);
        result = serializationValueOrThrow(codec->deserialize(object->getGame(), payload, context));
    } catch (const CSerializationException &exception) {
        auto error = exception.getError();
        completeError(error, context, object->meta()->name());
        throw CSerializationException(std::move(error));
    } catch (const std::exception &exception) {
        throw CSerializationException({CSerializationErrorCode::CodecFailure, context.source(), context.path(),
                                       object->meta()->name(), exception.what()});
    }
    const auto resultType = std::type_index(result.type());
    if (CTypes::is_pointer_type(resultType)) {
        object->setProperty(key, vstd::any_cast<std::shared_ptr<CGameObject>>(result));
    } else if (CTypes::is_array_type(resultType)) {
        if (context.isStrict() && key == "objects") {
            if (auto map = std::dynamic_pointer_cast<CMap>(object)) {
                map->setObjectsChecked(vstd::any_cast<std::set<std::shared_ptr<CMapObject>>>(result));
                return;
            }
        }
        object->setProperty(key, vstd::any_cast<std::set<std::shared_ptr<CGameObject>>>(result));
    } else if (CTypes::is_map_type(resultType)) {
        object->setProperty(key, vstd::any_cast<std::map<std::string, std::shared_ptr<CGameObject>>>(result));
    } else {
        CTypes::set_custom_property(object, key, result);
    }
}

void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::string &value) {
    (*object)[key] = value;
}

void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::shared_ptr<json> &value) {
    (*object)[key] = *value;
}

void add_member(const std::shared_ptr<json> &object, const std::string &key, bool value) { (*object)[key] = value; }

void add_member(const std::shared_ptr<json> &object, const std::string &key, int value) { (*object)[key] = value; }

void add_arr_member(const std::shared_ptr<json> &object, const std::string &value) {
    (*object)[object->size()] = value;
}

void add_arr_member(const std::shared_ptr<json> &object, const std::shared_ptr<json> &value) {
    (*object)[object->size()] = *value;
}

void add_arr_member(const std::shared_ptr<json> &object, bool value) { (*object)[object->size()] = value; }

void add_arr_member(const std::shared_ptr<json> &object, int value) { (*object)[object->size()] = value; }

void CSerialization::setProperty(const std::shared_ptr<json> &conf, const std::string &propertyName,
                                 const std::any &propertyValue) {
    CSerializationWriteContext context;
    setProperty(conf, propertyName, propertyValue, context);
}

void CSerialization::setProperty(const std::shared_ptr<json> &conf, const std::string &propertyName,
                                 const std::any &propertyValue, CSerializationWriteContext &context) {
    CSerializationOperation scope(context);
    CSerializationWriteContext::PropertyScope propertyScope(context, propertyName);
    const auto propertyType = std::type_index(propertyValue.type());
    if (propertyType == std::type_index(typeid(int))) {
        add_member(conf, propertyName, vstd::any_cast<int>(propertyValue));
    } else if (propertyType == std::type_index(typeid(std::string))) {
        add_member(conf, propertyName, vstd::any_cast<std::string>(propertyValue));
    } else if (propertyType == std::type_index(typeid(bool))) {
        add_member(conf, propertyName, vstd::any_cast<bool>(propertyValue));
    } else {
        if (CTypes::is_pointer_type(propertyType)) {
            auto primitiveValues =
                primitiveValuesConfig(vstd::any_cast<std::shared_ptr<CGameObject>>(propertyValue), context);
            if (primitiveValues) {
                add_member(conf, propertyName, primitiveValues);
                if (scope.isRoot())
                    context.finish(*conf);
                return;
            }
        }
        auto serializer = CTypes::findCodec(propertyType);
        if (serializer) {
            auto result = serializer->serialize(propertyValue, context);
            if (!result) {
                auto error = std::move(result.error());
                completeError(error, context, propertyType.name());
                throw CSerializationException(std::move(error));
            }
            (*conf)[propertyName] = std::move(*result);
        } else {
            throw CSerializationException({CSerializationErrorCode::MissingCodec, context.source(), context.path(),
                                           context.objectType().empty() ? propertyType.name() : context.objectType(),
                                           "No JSON codec registered for reflected property"});
        }
    }
    if (scope.isRoot())
        context.finish(*conf);
}

std::shared_ptr<json> object_serialize(const std::shared_ptr<CGameObject> &object) {
    return std::make_shared<json>(serializationValueOrThrow(CSerialization::serializeExpected(object)));
}

std::shared_ptr<json> object_serialize(const std::shared_ptr<CGameObject> &object,
                                       CSerializationWriteContext &context) {
    auto &state = context.state();
    ObjectDepthScope depth(state.objectDepth);
    auto config = std::make_shared<json>();
    if (object) {
        CSerializationWriteContext::PropertyScope objectScope(context, {}, object->meta()->name());
        add_member(config, "class", object->getType().empty() ? object->meta()->name() : object->getType());
        if (!state.effects.writeRecord(object, config))
            return config;
        auto properties = std::make_shared<json>();
        object->meta()->for_all_properties(object, [&](auto property) {
            if (property->name() != "type")
                CSerialization::setProperty(properties, property->name(),
                                            object->getProperty<std::any>(property->name()), context);
        });
        add_member(config, "properties", properties);
        state.effects.complete(object);
    }
    return config;
}

std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game,
                                                const std::shared_ptr<json> &config) {
    CSerializationReadContext context;
    return object_deserialize(game, config, context);
}

std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &config,
                                                CSerializationReadContext &context) {
    CSerializationOperation scope(context);
    const json *payload = config.get();
    if (scope.isRoot() && config)
        payload = &context.prepare(game, *config);
    auto object = object_deserialize(game, payload, context);
    if (scope.isRoot())
        context.finish(game);
    return object;
}

std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game, const json *config,
                                                CSerializationReadContext &context) {
    if (!game || !config || !config->is_object()) {
        if (context.isStrict())
            throw CSerializationException({CSerializationErrorCode::InvalidInput, context.source(), context.path(),
                                           context.objectType(),
                                           "Cannot deserialize a missing or non-object game object"});
        return nullptr;
    }
    auto &state = context.state();
    ObjectDepthScope depth(state.objectDepth);
    auto &effects = state.effects;
    effects.prepare(game, config);
    if (config->contains("effectActorReference"))
        return effects.reference(game, config, context);
    if (effects.alreadyLoading(config))
        return effects.definition(config);
    std::shared_ptr<CGameObject> object;
    if (CJsonUtil::isRef(config)) {
        object = game->getObjectHandler()->createObject(game, (*config)["ref"].get<std::string>(), context);
    } else if (CJsonUtil::isType(config)) {
        object = effects.definition(config);
        if (!object)
            object = game->getObjectHandler()->getType((*config)["class"].get<std::string>());
        if (object) {
            object->setGame(game);
            if (object->getName().empty())
                object->setName(CSerialization::generateName(object));
            object->setType((*config)["class"].get<std::string>());
        }
    }
    effects.readRecord(object, config);
    if (!object && context.isStrict()) {
        std::string type = "<unknown>";
        if (config->contains("ref") && (*config)["ref"].is_string())
            type = (*config)["ref"].get<std::string>();
        else if (config->contains("class") && (*config)["class"].is_string())
            type = (*config)["class"].get<std::string>();
        throw CSerializationException({CSerializationErrorCode::InvalidInput, context.source(), context.path(), type,
                                       "Cannot deserialize unresolved game object: " + type});
    }
    if (object && config->contains("properties")) {
        CGameObject::PropertyNotificationBatch notificationBatch(*object);
        for (const auto &[key, value] : (*config)["properties"].items()) {
            try {
                CSerialization::setProperty(object, key, value, context);
            } catch (const std::exception &exception) {
                if (context.isStrict())
                    throw;
                vstd::logger::warning("Skipping malformed property:", key, exception.what());
            }
        }
    }
    effects.initialize(object);
    effects.complete(config);
    return object;
}

std::shared_ptr<CGameObject> CSerialization::cloneObject(const std::shared_ptr<CGameObject> &object) {
    if (!object)
        return nullptr;
    CSerializationWriteContext writing({}, false);
    auto document = serializationValueOrThrow(serializeExpected(object, writing));
    CSerializationReadContext reading(false, {}, writing.externalActors());
    return serializationValueOrThrow(
        deserializeExpected<std::shared_ptr<CGameObject>>(object->getGame(), document, reading));
}

std::string CSerialization::generateName(const std::shared_ptr<CGameObject> &object) {
    return generateName(object, [&object](const std::string &candidate) {
        auto game = object ? object->getGame() : nullptr;
        auto map = game ? game->getMap() : nullptr;
        return map && map->getObjectByName(candidate) != nullptr;
    });
}

class CSerialization::NameFixtureScopeForTests::State {
  public:
    NameGenerationState names;
    std::uint64_t productionSequence = 0;
};

CSerialization::NameFixtureScopeForTests::NameFixtureScopeForTests(std::optional<std::uint32_t> seed)
    : previous(std::make_unique<State>()) {
    if (!vstd::event_loop<>::instance()->isMainThread()) {
        throw std::logic_error("Native name fixtures require the engine owner thread and serial use.");
    }
    std::lock_guard lock(nameGenerationMutex());
    previous->names = nameGenerationState();
    previous->productionSequence = productionNameSequence().load();
    nameGenerationState() = {};
    nameGenerationState().fixtureSeed = seed;
    productionNameSequence().store(0);
    fixtureNamesEnabled().store(seed.has_value(), std::memory_order_release);
}

CSerialization::NameFixtureScopeForTests::~NameFixtureScopeForTests() {
    std::lock_guard lock(nameGenerationMutex());
    nameGenerationState() = previous->names;
    productionNameSequence().store(previous->productionSequence);
    fixtureNamesEnabled().store(previous->names.fixtureSeed.has_value(), std::memory_order_release);
}

void CSerialization::seedGeneratedNamesForTests(std::uint32_t seed) {
    std::lock_guard lock(nameGenerationMutex());
    auto &state = nameGenerationState();
    if (state.sessionStarted || state.startupSeeded) {
        throw std::logic_error("Test random seeding must run once before the first game session is created.");
    }
    state.fixtureSeed = seed;
    state.fixtureSequence = 0;
    state.startupSeeded = true;
    fixtureNamesEnabled().store(true, std::memory_order_release);
}

void CSerialization::markGameSessionStarted() {
    std::lock_guard lock(nameGenerationMutex());
    nameGenerationState().sessionStarted = true;
}

std::string CSerialization::generateName(const std::shared_ptr<CGameObject> &object,
                                         const std::function<bool(const std::string &)> &isNameTaken) {
    // A colliding generated name silently drops the newcomer from name-keyed registries such as
    // CMap::mapObjects, so candidates are re-rolled until free. The sequence counter keeps hash
    // inputs distinct even when the allocator reuses an object address and the RNG repeats.
    constexpr int maxAttempts = 256;
    for (int attempt = 0; attempt < maxAttempts; attempt++) {
        auto candidate = [&]() {
            if (fixtureNamesEnabled().load(std::memory_order_acquire)) {
                std::lock_guard lock(nameGenerationMutex());
                auto &state = nameGenerationState();
                if (state.fixtureSeed) {
                    // Names do not consume a different gameplay stream in seeded fixtures.
                    static_cast<void>(vstd::rand());
                    return "fixture-" + std::to_string(*state.fixtureSeed) + "-" +
                           std::to_string(state.fixtureSequence++);
                }
            }
            return vstd::to_hex_hash(to_hex(object), vstd::rand(), productionNameSequence().fetch_add(1));
        }();
        if (!isNameTaken || !isNameTaken(candidate)) {
            return candidate;
        }
    }
    throw std::runtime_error("Failed to generate a unique object name after " + std::to_string(maxAttempts) +
                             " attempts");
}

std::shared_ptr<json> map_serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &objects) {
    CSerializationWriteContext context;
    CSerializationOperation scope(context);
    auto result = map_serialize(objects, context);
    context.finish(*result);
    return result;
}

std::shared_ptr<json> map_serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &objects,
                                    CSerializationWriteContext &context) {
    auto result = std::make_shared<json>();
    const bool independentEntries = context.isRootOperation() && context.state().objectDepth == 0;
    for (const auto &[key, object] : objects)
        add_member(result, key, independentEntries ? object_serialize(object) : object_serialize(object, context));
    return result;
}

std::map<std::string, std::shared_ptr<CGameObject>> map_deserialize(const std::shared_ptr<CGame> &game,
                                                                    const std::shared_ptr<json> &document) {
    CSerializationReadContext context;
    CSerializationOperation scope(context);
    const json *payload = document.get();
    if (document)
        payload = &context.prepare(game, *document);
    auto result = map_deserialize(game, payload, context);
    context.finish(game);
    return result;
}

std::map<std::string, std::shared_ptr<CGameObject>>
map_deserialize(const std::shared_ptr<CGame> &game, const json *document, CSerializationReadContext &context) {
    std::map<std::string, std::shared_ptr<CGameObject>> result;
    if (!document || !document->is_object())
        return result;
    const bool independentEntries =
        context.isRootOperation() && context.state().objectDepth == 0 && !context.state().effects.hasGraph();
    for (const auto &[key, value] : document->items()) {
        CSerializationReadContext::PropertyScope path(context, key);
        std::shared_ptr<CGameObject> object;
        if (independentEntries) {
            CSerializationReadContext entryContext(context.isStrict(), context.source());
            CSerializationOperation entryScope(entryContext);
            entryContext.prepare(game, value);
            object = object_deserialize(game, &value, entryContext);
            entryContext.finish(game);
        } else {
            object = object_deserialize(game, &value, context);
        }
        if (object)
            result.emplace(key, std::move(object));
        else if (context.isStrict())
            throw CSerializationException({CSerializationErrorCode::InvalidInput, context.source(), context.path(),
                                           context.objectType(),
                                           "Failed to deserialize object in map property '" + key + "'"});
    }
    return result;
}

std::shared_ptr<json> array_serialize(const std::set<std::shared_ptr<CGameObject>> &objects) {
    CSerializationWriteContext context;
    CSerializationOperation scope(context);
    auto result = array_serialize(objects, context);
    context.finish(*result);
    return result;
}

std::shared_ptr<json> array_serialize(const std::set<std::shared_ptr<CGameObject>> &objects,
                                      CSerializationWriteContext &context) {
    auto result = std::make_shared<json>();
    const bool independentEntries = context.isRootOperation() && context.state().objectDepth == 0;
    for (const auto &object : objects)
        add_arr_member(result, independentEntries ? object_serialize(object) : object_serialize(object, context));
    return result;
}

std::set<std::shared_ptr<CGameObject>> array_deserialize(const std::shared_ptr<CGame> &game,
                                                         const std::shared_ptr<json> &document) {
    CSerializationReadContext context;
    CSerializationOperation scope(context);
    const json *payload = document.get();
    if (document)
        payload = &context.prepare(game, *document);
    auto result = array_deserialize(game, payload, context);
    context.finish(game);
    return result;
}

std::set<std::shared_ptr<CGameObject>> array_deserialize(const std::shared_ptr<CGame> &game, const json *document,
                                                         CSerializationReadContext &context) {
    std::set<std::shared_ptr<CGameObject>> result;
    if (!document || !document->is_array())
        return result;
    const bool independentEntries =
        context.isRootOperation() && context.state().objectDepth == 0 && !context.state().effects.hasGraph();
    for (std::size_t index = 0; index < document->size(); ++index) {
        CSerializationReadContext::PropertyScope path(context, "[" + std::to_string(index) + "]", {}, true);
        const auto &entry = (*document)[index];
        if (!entry.is_object()) {
            if (context.isStrict() && !shouldSkipInvalidArrayEntryInStrictMode(context))
                throw CSerializationException({CSerializationErrorCode::InvalidInput, context.source(), context.path(),
                                               context.objectType(),
                                               "Cannot deserialize a missing or non-object game object"});
            vstd::logger::warning("Failed to deserialize object in array", context.path(),
                                  "- skipping non-object entry");
            continue;
        }
        std::shared_ptr<CGameObject> object;
        if (independentEntries) {
            CSerializationReadContext entryContext(context.isStrict(), context.source());
            CSerializationOperation entryScope(entryContext);
            entryContext.prepare(game, entry);
            object = object_deserialize(game, &entry, entryContext);
            entryContext.finish(game);
        } else {
            object = object_deserialize(game, &entry, context);
        }
        if (!object) {
            if (context.isStrict())
                throw CSerializationException(
                    {CSerializationErrorCode::InvalidInput, context.source(), context.path(), context.objectType(),
                     "Failed to deserialize object in array at index " + std::to_string(index)});
            vstd::logger::warning("Failed to deserialize object in array", context.path(), "- skipping null entry");
        } else {
            result.insert(std::move(object));
        }
    }
    return result;
}

std::type_index CSerialization::getGenericPropertyType(const json *document) {
    if (CJsonUtil::isObject(document))
        return std::type_index(typeid(std::shared_ptr<CGameObject>));
    if (CJsonUtil::isMap(document))
        return std::type_index(typeid(std::map<std::string, std::shared_ptr<CGameObject>>));
    vstd::logger::warning("Unable to determine JSON property type; treating as object pointer");
    return std::type_index(typeid(std::shared_ptr<CGameObject>));
}

std::shared_ptr<json> CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::serialize(
    const std::set<std::shared_ptr<CGameObject>> &objects) {
    return array_serialize(objects);
}

std::set<std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::deserialize(
    const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &document) {
    return array_deserialize(game, document);
}

std::set<std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::deserialize(
    const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &document, CSerializationReadContext &context) {
    CSerializationOperation scope(context);
    const json *payload = document.get();
    if (scope.isRoot() && document)
        payload = &context.prepare(game, *document);
    auto result = array_deserialize(game, payload, context);
    if (scope.isRoot())
        context.finish(game);
    return result;
}

std::shared_ptr<json>
CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>>::serialize(
    const std::map<std::string, std::shared_ptr<CGameObject>> &objects) {
    return map_serialize(objects);
}

std::map<std::string, std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(
    const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &document) {
    return map_deserialize(game, document);
}

std::map<std::string, std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(
    const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &document, CSerializationReadContext &context) {
    CSerializationOperation scope(context);
    const json *payload = document.get();
    if (scope.isRoot() && document)
        payload = &context.prepare(game, *document);
    auto result = map_deserialize(game, payload, context);
    if (scope.isRoot())
        context.finish(game);
    return result;
}

std::shared_ptr<CGameObject> CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
    const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &document) {
    return object_deserialize(game, document);
}
std::shared_ptr<CGameObject> CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
    const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &document, CSerializationReadContext &context) {
    return object_deserialize(game, document, context);
}
std::shared_ptr<json> CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(
    const std::shared_ptr<CGameObject> &object) {
    return object_serialize(object);
}
