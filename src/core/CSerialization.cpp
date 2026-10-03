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
#include "core/CSerialization.h"
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

std::shared_ptr<CSerializerBase> CSerialization::serializer(std::pair<std::type_index, std::type_index> key) {
    return (*CTypes::serializers())[key];
}

namespace {
thread_local std::string array_deserialize_context;
thread_local bool strict_deserialization = false;

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

    void finish(const std::shared_ptr<json> &root) {
        auto detached = json::array();
        if (includeDetached) {
            // Serializing a detached actor can discover further actors; the growing queue visits each once.
            for (std::size_t index = 0; index < actors.size(); ++index) {
                if (!actors[index].defined) {
                    auto actor = actors[index].actor;
                    detached[detached.size()] = *object_serialize(actor);
                }
            }
        }
        if (!actors.empty()) {
            (*root)["effectGraph"] = {{"version", 1}, {"actors", std::move(detached)}};
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
    explicit EffectReadContext(std::unordered_map<int, std::shared_ptr<CCreature>> external = {})
        : actors(std::move(external)) {}

    [[noreturn]] void fail(const std::string &message) {
        failure = "Invalid effect graph: " + message;
        throw std::runtime_error(failure);
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

    void prepare(const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &config) {
        if (!config->contains("effectGraph")) {
            return;
        }
        if (graph) {
            if (graphRoot != config.get()) {
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
        graphRoot = config.get();
        graph = CJsonUtil::alias(config, value);

        // Allocate actor identities before setting properties: a forward alias can precede its definition in JSON.
        std::vector<json *> pending{config.get()};
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
                    definitions.emplace(id, CJsonUtil::alias(config, *node));
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

    std::shared_ptr<CCreature> definition(const std::shared_ptr<json> &config) {
        if (!config->contains("effectActorId")) {
            return nullptr;
        }
        const int id = readId((*config)["effectActorId"]);
        if (!graph || !definitions.contains(id) || definitions.at(id).get() != config.get()) {
            fail("actor definition is outside its snapshot graph");
        }
        loadedDefinitions.insert(id);
        return actors.at(id);
    }

    bool alreadyLoading(const std::shared_ptr<json> &config) {
        return config->contains("effectActorId") && loadedDefinitions.contains(readId((*config)["effectActorId"]));
    }

    std::shared_ptr<CCreature> reference(const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &config) {
        const int id = readId((*config)["effectActorReference"]);
        if (!graph || !actors.contains(id) || config->size() != 2 || !config->contains("class") ||
            !(*config)["class"].is_string()) {
            fail("dangling or malformed actor alias");
        }
        if (definitions.contains(id) && !loadedDefinitions.contains(id)) {
            // CMap indexes actors as soon as its objects setter runs; populate a forward alias before returning it.
            object_deserialize(game, definitions.at(id));
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

    void readRecord(const std::shared_ptr<CGameObject> &object, const std::shared_ptr<json> &config) {
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

    void complete(const std::shared_ptr<json> &config) {
        if (config->contains("effectActorId")) {
            completedDefinitions.insert(readId((*config)["effectActorId"]));
        }
    }

    void finish(const std::shared_ptr<CGame> &game) {
        if (graph) {
            for (auto &record : (*graph)["actors"]) {
                if (!record.is_object() || !record.contains("effectActorId")) {
                    fail("detached actor table contains a non-definition");
                }
                if (!object_deserialize(game, CJsonUtil::alias(graph, record))) {
                    fail("detached actor could not be loaded");
                }
            }
        }
        if (!failure.empty()) {
            throw std::runtime_error(failure);
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
    const json *graphRoot = nullptr;
    std::shared_ptr<json> graph;
    bool needsFixup = false;
    std::string failure;
    std::unordered_map<int, std::shared_ptr<CCreature>> actors;
    std::unordered_map<int, std::shared_ptr<json>> definitions;
    std::unordered_set<int> loadedDefinitions;
    std::unordered_set<int> completedDefinitions;
    std::vector<EffectLinks> effects;
    std::vector<std::shared_ptr<CGameObject>> initializations;
    std::unordered_set<const CGameObject *> initializationSet;
};

thread_local EffectWriteContext *effectWriteContext = nullptr;
thread_local EffectReadContext *effectReadContext = nullptr;

template <typename Context> class EffectContextScope {
  public:
    EffectContextScope(Context *&slot, Context &context) : slot(slot), previous(slot) { slot = &context; }
    ~EffectContextScope() { slot = previous; }

  private:
    Context *&slot;
    Context *previous;
};

class CScopedArrayDeserializeContext {
  public:
    explicit CScopedArrayDeserializeContext(std::string context) : previous(array_deserialize_context) {
        array_deserialize_context = std::move(context);
    }

    ~CScopedArrayDeserializeContext() { array_deserialize_context = previous; }

  private:
    std::string previous;
};

bool shouldSkipInvalidArrayEntryInStrictMode() {
    return array_deserialize_context.find("property 'quests'") != std::string::npos ||
           array_deserialize_context.find("property 'completedQuests'") != std::string::npos;
}

std::shared_ptr<json> primitiveValuesConfig(const std::shared_ptr<CGameObject> &object) {
    if (!object || !CTypes::isPrimitiveType(std::type_index(typeid(*object))) ||
        !object->meta()->has_property("values", object)) {
        return nullptr;
    }

    auto values = std::make_shared<json>();
    CSerialization::setProperty(values, "values", object->getProperty<std::any>("values"));
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

template <typename T>
bool isCompatiblePrimitiveObjectConfig(const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &value) {
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

template <typename T>
bool shouldKeepPrimitiveObjectConfig(const std::shared_ptr<CGame> &game, const std::shared_ptr<json> &value) {
    if (!CJsonUtil::isObject(value)) {
        return false;
    }
    return !isPrimitiveMapWrapper<T>() || value->contains("properties") ||
           isCompatiblePrimitiveObjectConfig<T>(game, value);
}

template <typename T>
std::shared_ptr<json> primitiveObjectConfig(const std::shared_ptr<CGame> &game, std::type_index property,
                                            const std::shared_ptr<json> &value) {
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
                                            const std::shared_ptr<json> &value) {
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
bool rejectScalarForPrimitiveCollection(std::type_index property, const std::string &key) {
    if (!isPrimitiveCollectionPointer(property)) {
        return false;
    }
    const std::string message = "Cannot deserialize scalar value for property '" + key +
                                "' which expects a primitive collection wrapper (a JSON array or object is required)";
    if (CSerialization::isStrict()) {
        throw std::runtime_error(message);
    }
    vstd::logger::warning(message);
    return true;
}

class CGameObjectPointerSerializer : public CSerializerBase {
  public:
    std::any serialize(std::any object) final {
        return std::any(object_serialize(vstd::any_cast<std::shared_ptr<CGameObject>>(object)));
    }

    std::any deserialize(std::shared_ptr<CGame> map, std::any object) final {
        return std::any(object_deserialize(map, vstd::any_cast<std::shared_ptr<json>>(object)));
    }
};

class CGameObjectSetSerializer : public CSerializerBase {
  public:
    std::any serialize(std::any object) final {
        return std::any(array_serialize(vstd::any_cast<std::set<std::shared_ptr<CGameObject>>>(object)));
    }

    std::any deserialize(std::shared_ptr<CGame> map, std::any object) final {
        return std::any(array_deserialize(map, vstd::any_cast<std::shared_ptr<json>>(object)));
    }
};

class CGameObjectMapSerializer : public CSerializerBase {
  public:
    std::any serialize(std::any object) final {
        return std::any(map_serialize(vstd::any_cast<std::map<std::string, std::shared_ptr<CGameObject>>>(object)));
    }

    std::any deserialize(std::shared_ptr<CGame> map, std::any object) final {
        return std::any(map_deserialize(map, vstd::any_cast<std::shared_ptr<json>>(object)));
    }
};
} // namespace

CSerialization::StrictScope::StrictScope() : previous(CSerialization::setStrict(true)) {}

CSerialization::StrictScope::~StrictScope() { CSerialization::setStrict(previous); }

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
    if (!object || !value) {
        return;
    }
    if (value->is_boolean()) {
        setBooleanProperty(object, key, value->get<bool>());
    } else if (value->is_number()) {
        setNumericProperty(object, key, value->get<int>());
    } else if (value->is_string()) {
        setStringProperty(object, key, value->get<std::string>());
    } else if (value->is_array()) {
        setArrayProperty(object, getProperty(object, key), key, value);
    } else if (value->is_object()) {
        setObjectProperty(object, getProperty(object, key), key, value);
    }
}

std::type_index CSerialization::getProperty(const std::shared_ptr<CGameObject> &object, const std::string &name) {
    return object->meta()->get_property_type(object, name);
}

void CSerialization::setArrayProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                      const std::string &key, std::shared_ptr<json> value) {
    if (auto config = primitiveObjectConfig(object->getGame(), property, value)) {
        setOtherProperty(std::type_index(typeid(std::shared_ptr<json>)), property, object, key, std::any(config));
        return;
    }
    setOtherProperty(std::type_index(typeid(std::shared_ptr<json>)),
                     property != V_VOID ? property : std::type_index(typeid(std::set<std::shared_ptr<CGameObject>>)),
                     object, key, std::any(value));
}

void CSerialization::setObjectProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                       const std::string &key, std::shared_ptr<json> value) {
    if (auto config = primitiveObjectConfig(object->getGame(), property, value)) {
        setOtherProperty(std::type_index(typeid(std::shared_ptr<json>)), property, object, key, std::any(config));
        return;
    }
    setOtherProperty(std::type_index(typeid(std::shared_ptr<json>)),
                     property != V_VOID ? property : getGenericPropertyType(value), object, key, std::any(value));
}

void CSerialization::setNumericProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, int value) {
    if (isString(object, key)) {
        object->setStringProperty(key, vstd::str(value));
    } else if (!rejectScalarForPrimitiveCollection(getProperty(object, key), key)) {
        object->setNumericProperty(key, value);
    }
}

void CSerialization::setBooleanProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                        bool value) {
    if (isString(object, key)) {
        object->setStringProperty(key, vstd::str(value));
    } else if (!rejectScalarForPrimitiveCollection(getProperty(object, key), key)) {
        object->setBoolProperty(key, value);
    }
}

void CSerialization::setStringProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                       const std::string &value) {
    auto coerced = coerceStringProperty(getProperty(object, key), value);
    if (std::holds_alternative<std::string>(coerced)) {
        if (!rejectScalarForPrimitiveCollection(getProperty(object, key), key)) {
            object->setStringProperty(key, std::get<std::string>(coerced));
        }
    } else if (std::holds_alternative<int>(coerced)) {
        setNumericProperty(object, key, std::get<int>(coerced));
    } else if (std::holds_alternative<bool>(coerced)) {
        setBooleanProperty(object, key, std::get<bool>(coerced));
    } else if (std::holds_alternative<std::shared_ptr<json>>(coerced)) {
        setProperty(object, key, std::get<std::shared_ptr<json>>(coerced));
    }
}

bool CSerialization::isString(const std::shared_ptr<CGameObject> &object, const std::string &key) {
    return getProperty(object, key) == std::type_index(typeid(std::string));
}

void CSerialization::setOtherProperty(std::type_index serializedId, std::type_index deserializedId,
                                      const std::shared_ptr<CGameObject> &object, const std::string &key,
                                      const std::any &value) {
    std::shared_ptr<CSerializerBase> serializer =
        vstd::ctn(*CTypes::serializers(), std::make_pair(serializedId, deserializedId))
            ? (*CTypes::serializers())[std::make_pair(serializedId, deserializedId)]
            : nullptr;
    if (!serializer) {
        vstd::logger::warning("No serializer for property:", key);
        return;
    }
    std::any result;
    try {
        std::string context = "property '" + key + "'";
        if (object) {
            context += " on ";
            context += vstd::is_empty(object->getTypeId()) ? object->meta()->name() : object->getTypeId();
            if (!vstd::is_empty(object->getName())) {
                context += " named '" + object->getName() + "'";
            }
        }
        CScopedArrayDeserializeContext arrayContext(context);
        result = vstd::not_null(serializer, "No serializer!")->deserialize(object->getGame(), value);
    } catch (const std::exception &ex) {
        throw std::runtime_error("Failed to deserialize property '" + key + "': " + ex.what());
    }
    const auto resultType = std::type_index(result.type());
    if (CTypes::is_pointer_type(resultType)) {
        object->setProperty(key, vstd::any_cast<std::shared_ptr<CGameObject>>(result));
    } else if (CTypes::is_array_type(resultType)) {
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
    const auto propertyType = std::type_index(propertyValue.type());
    if (propertyType == std::type_index(typeid(int))) {
        add_member(conf, propertyName, vstd::any_cast<int>(propertyValue));
    } else if (propertyType == std::type_index(typeid(std::string))) {
        add_member(conf, propertyName, vstd::any_cast<std::string>(propertyValue));
    } else if (propertyType == std::type_index(typeid(bool))) {
        add_member(conf, propertyName, vstd::any_cast<bool>(propertyValue));
    } else {
        if (CTypes::is_pointer_type(propertyType)) {
            auto primitiveValues = primitiveValuesConfig(vstd::any_cast<std::shared_ptr<CGameObject>>(propertyValue));
            if (primitiveValues) {
                add_member(conf, propertyName, primitiveValues);
                return;
            }
        }
        std::shared_ptr<CSerializerBase> serializer;
        for (const auto &entry : *CTypes::serializers()) {
            auto types = entry.first;
            if (types.second == propertyType) {
                vstd::fail_if(serializer, "Ambiguous serializer!");
                serializer = entry.second;
            }
        }
        if (serializer) {
            add_member(conf, propertyName, vstd::any_cast<std::shared_ptr<json>>(serializer->serialize(propertyValue)));
        } else {
            vstd::logger::warning("No serializer for:", propertyName);
        }
    }
}

std::shared_ptr<json> object_serialize(const std::shared_ptr<CGameObject> &object) {
    if (!effectWriteContext) {
        EffectWriteContext context;
        EffectContextScope scope(effectWriteContext, context);
        auto config = object_serialize(object);
        context.finish(config);
        return config;
    }
    std::shared_ptr<json> conf = std::make_shared<json>();
    if (object) {
        add_member(conf, "class", vstd::is_empty(object->getType()) ? object->meta()->name() : object->getType());
        if (!effectWriteContext->writeRecord(object, conf)) {
            return conf;
        }
        std::shared_ptr<json> properties = std::make_shared<json>();
        object->meta()->for_all_properties(object, [&](auto property) {
            if (property->name() != "type") {
                CSerialization::setProperty(properties, property->name(),
                                            object->getProperty<std::any>(property->name()));
            }
        });
        add_member(conf, "properties", properties);
        effectWriteContext->complete(object);
    }
    return conf;
}

std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game,
                                                const std::shared_ptr<json> &config) {
    if (!effectReadContext) {
        EffectReadContext context;
        EffectContextScope scope(effectReadContext, context);
        auto object = object_deserialize(game, config);
        context.finish(game);
        return object;
    }
    std::shared_ptr<CGameObject> object;
    if (!game || !config || !config->is_object()) {
        if (CSerialization::isStrict()) {
            throw std::runtime_error("Cannot deserialize a missing or non-object game object");
        }
        return nullptr;
    }
    effectReadContext->prepare(game, config);
    if (config->contains("effectActorReference")) {
        return effectReadContext->reference(game, config);
    }
    if (effectReadContext->alreadyLoading(config)) {
        return effectReadContext->definition(config);
    }
    if (CJsonUtil::isRef(config)) {
        object = game->getObjectHandler()->createObject(game, (*config)["ref"].get<std::string>());
    } else if (CJsonUtil::isType(config)) {
        object = effectReadContext->definition(config);
        if (!object) {
            object = game->getObjectHandler()->getType((*config)["class"].get<std::string>());
        }
        if (object) {
            object->setGame(game);
            if (vstd::is_empty(object->getName())) {
                object->setName(CSerialization::generateName(object));
            }
            object->setType((*config)["class"].get<std::string>());
        }
    }
    effectReadContext->readRecord(object, config);
    if (!object && CSerialization::isStrict()) {
        std::string type = "<unknown>";
        if (config->contains("ref") && (*config)["ref"].is_string()) {
            type = (*config)["ref"].get<std::string>();
        } else if (config->contains("class") && (*config)["class"].is_string()) {
            type = (*config)["class"].get<std::string>();
        }
        throw std::runtime_error("Cannot deserialize unresolved game object: " + type);
    }
    if (object && config->is_object() && config->count("properties")) {
        auto properties = &(*config)["properties"];
        CGameObject::PropertyNotificationBatch notificationBatch(*object);
        for (auto &[key, value] : properties->items()) {
            try {
                CSerialization::setProperty(object, key, CJsonUtil::alias(config, value));
            } catch (const std::exception &exception) {
                if (CSerialization::isStrict()) {
                    throw;
                }
                vstd::logger::warning("Skipping malformed property:", key, exception.what());
            }
        }
    }
    effectReadContext->initialize(object);
    effectReadContext->complete(config);
    return object;
}

std::shared_ptr<CGameObject> CSerialization::cloneObject(const std::shared_ptr<CGameObject> &object) {
    if (!object) {
        return nullptr;
    }
    EffectWriteContext writing(false);
    std::shared_ptr<json> config;
    {
        EffectContextScope writeScope(effectWriteContext, writing);
        config = object_serialize(object);
        writing.finish(config);
    }
    EffectReadContext reading(writing.externalActors());
    EffectContextScope readScope(effectReadContext, reading);
    auto clone = object_deserialize(object->getGame(), config);
    reading.finish(object->getGame());
    return clone;
}

std::string CSerialization::generateName(const std::shared_ptr<CGameObject> &object) {
    return generateName(object, [&object](const std::string &candidate) {
        auto game = object ? object->getGame() : nullptr;
        auto map = game ? game->getMap() : nullptr;
        return map && map->getObjectByName(candidate) != nullptr;
    });
}

std::string CSerialization::generateName(const std::shared_ptr<CGameObject> &object,
                                         const std::function<bool(const std::string &)> &isNameTaken) {
    // A colliding generated name silently drops the newcomer from name-keyed registries such as
    // CMap::mapObjects, so candidates are re-rolled until free. The sequence counter keeps hash
    // inputs distinct even when the allocator reuses an object address and the RNG repeats.
    static std::atomic<std::uint64_t> sequence{0};
    constexpr int maxAttempts = 256;
    for (int attempt = 0; attempt < maxAttempts; attempt++) {
        auto candidate = vstd::to_hex_hash(to_hex(object), vstd::rand(), sequence.fetch_add(1));
        if (!isNameTaken || !isNameTaken(candidate)) {
            return candidate;
        }
    }
    throw std::runtime_error("Failed to generate a unique object name after " + std::to_string(maxAttempts) +
                             " attempts");
}

std::shared_ptr<json> map_serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &object) {
    std::shared_ptr<json> ob = std::make_shared<json>();
    for (const auto &it : object) {
        add_member(ob, it.first,
                   CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(it.second));
    }
    return ob;
}

std::map<std::string, std::shared_ptr<CGameObject>> map_deserialize(const std::shared_ptr<CGame> &map,
                                                                    const std::shared_ptr<json> &object) {
    std::map<std::string, std::shared_ptr<CGameObject>> ret;
    if (!object || !object->is_object()) {
        return ret;
    }
    for (auto &[key, val] : object->items()) {
        auto deserialized = CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
            map, CJsonUtil::alias(object, val));
        if (deserialized) {
            ret[key] = deserialized;
        } else if (CSerialization::isStrict()) {
            throw std::runtime_error("Failed to deserialize object in map property '" + key + "'");
        }
    }
    return ret;
}

std::shared_ptr<json> array_serialize(const std::set<std::shared_ptr<CGameObject>> &set) {
    std::shared_ptr<json> arr = std::make_shared<json>();
    for (const auto &ob : set) {
        add_arr_member(arr, CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(ob));
    }
    return arr;
}

std::set<std::shared_ptr<CGameObject>> array_deserialize(const std::shared_ptr<CGame> &map,
                                                         const std::shared_ptr<json> &object) {
    std::set<std::shared_ptr<CGameObject>> objects;
    if (!object || !object->is_array()) {
        return objects;
    }
    for (unsigned int i = 0; i < object->size(); i++) {
        auto entry = CJsonUtil::alias(object, (*object)[i]);
        if (!entry || !entry->is_object()) {
            if (CSerialization::isStrict() && !shouldSkipInvalidArrayEntryInStrictMode()) {
                throw std::runtime_error("Cannot deserialize a missing or non-object game object");
            }
            vstd::logger::warning("Failed to deserialize object in array",
                                  array_deserialize_context.empty() ? "property <unknown>" : array_deserialize_context,
                                  "index", i, "- skipping non-object entry");
            continue;
        }
        auto deserialized =
            CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(map, entry);
        if (!deserialized) {
            if (CSerialization::isStrict()) {
                throw std::runtime_error("Failed to deserialize object in array at index " + std::to_string(i));
            }
            vstd::logger::warning("Failed to deserialize object in array",
                                  array_deserialize_context.empty() ? "property <unknown>" : array_deserialize_context,
                                  "index", i, "- skipping null entry");
            continue;
        }
        objects.insert(deserialized);
    }
    return objects;
}

std::type_index CSerialization::getGenericPropertyType(const std::shared_ptr<json> &object) {
    if (CJsonUtil::isObject(object)) {
        return std::type_index(typeid(std::shared_ptr<CGameObject>));
    } else if (CJsonUtil::isMap(object)) {
        return std::type_index(typeid(std::map<std::string, std::shared_ptr<CGameObject>>));
    }
    vstd::logger::warning("Unable to determine JSON property type; treating as object pointer");
    return std::type_index(typeid(std::shared_ptr<CGameObject>));
}

std::shared_ptr<json> CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::serialize(
    const std::set<std::shared_ptr<CGameObject>> &set) {
    return array_serialize(set);
}

std::set<std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>>::deserialize(
    const std::shared_ptr<CGame> &map, const std::shared_ptr<json> &object) {
    return array_deserialize(map, object);
}

std::shared_ptr<json>
CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>>::serialize(
    const std::map<std::string, std::shared_ptr<CGameObject>> &object) {
    return map_serialize(object);
}

std::map<std::string, std::shared_ptr<CGameObject>>
CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(
    const std::shared_ptr<CGame> &map, const std::shared_ptr<json> &object) {
    return map_deserialize(map, object);
}

std::shared_ptr<CGameObject> CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::deserialize(
    const std::shared_ptr<CGame> &map, const std::shared_ptr<json> &config) {
    return object_deserialize(map, config);
}

std::shared_ptr<json> CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>>::serialize(
    const std::shared_ptr<CGameObject> &object) {
    return object_serialize(object);
}

bool CSerialization::isStrict() { return strict_deserialization; }

bool CSerialization::setStrict(bool value) {
    const bool previous = strict_deserialization;
    strict_deserialization = value;
    return previous;
}
