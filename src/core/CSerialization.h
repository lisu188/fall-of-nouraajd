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
#pragma once

#include "core/CConcepts.h"
#include "core/CGlobal.h"
#include "core/CJsonUtil.h"

#include <expected>
#include <memory>
#include <optional>
#include <stdexcept>
#include <unordered_map>
#include <variant>
#include <vector>

class CGame;

class CGameObject;

class CSerializerBase;
class CCreature;

enum class CSerializationErrorCode { MissingCodec, InvalidInput, TypeMismatch, MalformedGraph, CodecFailure };

struct CSerializationError {
    CSerializationErrorCode code;
    std::string source;
    std::string propertyPath;
    std::string objectType;
    std::string message;
};

template <typename T> using CSerializationResult = std::expected<T, CSerializationError>;

class CSerializationWriteContext {
  public:
    class State;
    class PropertyScope {
      public:
        PropertyScope(CSerializationWriteContext &context, std::string property, std::string type = {});
        ~PropertyScope();
        PropertyScope(const PropertyScope &) = delete;
        PropertyScope &operator=(const PropertyScope &) = delete;

      private:
        CSerializationWriteContext &context;
        std::string previousPath;
        std::string previousType;
    };
    explicit CSerializationWriteContext(std::string source = {}, bool includeDetached = true);
    ~CSerializationWriteContext();
    CSerializationWriteContext(const CSerializationWriteContext &) = delete;
    CSerializationWriteContext &operator=(const CSerializationWriteContext &) = delete;
    CSerializationWriteContext(CSerializationWriteContext &&) = delete;
    CSerializationWriteContext &operator=(CSerializationWriteContext &&) = delete;
    bool begin();
    void end() noexcept;
    void finish(json &document);
    bool isRootOperation() const noexcept { return depth == 1; }
    State &state();
    const std::string &source() const noexcept { return sourceName; }
    const std::string &path() const noexcept { return propertyPath; }
    const std::string &objectType() const noexcept { return typeName; }
    std::unordered_map<int, std::shared_ptr<CCreature>> externalActors();

  private:
    std::string sourceName;
    std::string propertyPath;
    std::string typeName;
    bool includeDetached;
    std::size_t depth = 0;
    std::unique_ptr<State> operationState;
};

class CSerializationReadContext {
  public:
    class State;
    class PropertyScope {
      public:
        PropertyScope(CSerializationReadContext &context, std::string property, std::string type = {},
                      bool index = false);
        ~PropertyScope();
        PropertyScope(const PropertyScope &) = delete;
        PropertyScope &operator=(const PropertyScope &) = delete;

      private:
        CSerializationReadContext &context;
        std::string previousPath;
        std::string previousProperty;
        std::string previousType;
    };

    explicit CSerializationReadContext(bool strict = false, std::string source = {},
                                       std::unordered_map<int, std::shared_ptr<CCreature>> external = {});
    ~CSerializationReadContext();
    CSerializationReadContext(const CSerializationReadContext &) = delete;
    CSerializationReadContext &operator=(const CSerializationReadContext &) = delete;
    CSerializationReadContext(CSerializationReadContext &&) = delete;
    CSerializationReadContext &operator=(CSerializationReadContext &&) = delete;
    bool begin();
    void end() noexcept;
    void finish(const std::shared_ptr<CGame> &game);
    const json &prepare(const std::shared_ptr<CGame> &game, const json &document);
    bool isRootOperation() const noexcept { return depth == 1; }
    State &state();
    void keepDocument(std::shared_ptr<const json> document);
    bool isStrict() const noexcept { return strictPolicy; }
    const std::string &source() const noexcept { return sourceName; }
    const std::string &path() const noexcept { return propertyPath; }
    const std::string &property() const noexcept { return propertyName; }
    const std::string &objectType() const noexcept { return typeName; }

  private:
    bool strictPolicy;
    std::string sourceName;
    std::string propertyPath;
    std::string propertyName;
    std::string typeName;
    std::size_t depth = 0;
    std::unordered_map<int, std::shared_ptr<CCreature>> external;
    std::unique_ptr<State> operationState;
    std::vector<std::shared_ptr<const json>> documents;
};

template <typename Context> class CSerializationOperation {
  public:
    explicit CSerializationOperation(Context &context) : context(context), root(context.begin()) {}
    ~CSerializationOperation() { context.end(); }
    CSerializationOperation(const CSerializationOperation &) = delete;
    CSerializationOperation &operator=(const CSerializationOperation &) = delete;
    bool isRoot() const noexcept { return root; }

  private:
    Context &context;
    bool root;
};

class CSerializationException : public std::runtime_error {
  public:
    explicit CSerializationException(CSerializationError error)
        : std::runtime_error(error.message), error(std::move(error)) {}
    const CSerializationError &getError() const noexcept { return error; }

  private:
    CSerializationError error;
};

class CSerializerBase {
    friend class CSerialization;

  public:
    virtual ~CSerializerBase() = default;

    CSerializationResult<json> serialize(const std::any &object) const;
    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &object) const;

    virtual CSerializationResult<json> serialize(const std::any &object, CSerializationWriteContext &context) const = 0;
    virtual CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &object,
                                                       CSerializationReadContext &context) const = 0;
};

template <typename F> auto serializationResult(F &&operation) -> CSerializationResult<std::invoke_result_t<F>> {
    try {
        if constexpr (std::is_void_v<std::invoke_result_t<F>>) {
            std::invoke(std::forward<F>(operation));
            return {};
        } else {
            return std::invoke(std::forward<F>(operation));
        }
    } catch (const CSerializationException &exception) {
        return std::unexpected(exception.getError());
    } catch (const std::bad_any_cast &exception) {
        return std::unexpected(
            CSerializationError{CSerializationErrorCode::TypeMismatch, {}, {}, {}, exception.what()});
    } catch (const std::exception &exception) {
        return std::unexpected(
            CSerializationError{CSerializationErrorCode::CodecFailure, {}, {}, {}, exception.what()});
    }
}

template <typename T> T serializationValueOrThrow(CSerializationResult<T> result) {
    if (!result) {
        throw CSerializationException(std::move(result.error()));
    }
    if constexpr (!std::is_void_v<T>) {
        return std::move(*result);
    }
}

inline CSerializationResult<json> CSerializerBase::serialize(const std::any &object) const {
    return serializationResult([&]() -> json {
        CSerializationWriteContext context;
        CSerializationOperation scope(context);
        auto document = serializationValueOrThrow(serialize(object, context));
        context.finish(document);
        return document;
    });
}

inline CSerializationResult<std::any> CSerializerBase::deserialize(const std::shared_ptr<CGame> &game,
                                                                   const json &object) const {
    return serializationResult([&]() -> std::any {
        CSerializationReadContext context;
        CSerializationOperation scope(context);
        const auto &payload = context.prepare(game, object);
        auto value = serializationValueOrThrow(deserialize(game, payload, context));
        context.finish(game);
        return value;
    });
}

template <typename T> class CTypedJsonCodec final : public CSerializerBase {
  public:
    using Encoder = std::function<CSerializationResult<json>(const T &, CSerializationWriteContext &)>;
    using Decoder = std::function<CSerializationResult<T>(const std::shared_ptr<CGame> &, const json &,
                                                          CSerializationReadContext &)>;

    template <typename Encode, typename Decode>
    CTypedJsonCodec(Encode encode, Decode decode)
        : encoder([encode = std::move(encode)](
                      const T &value, CSerializationWriteContext &context) mutable -> CSerializationResult<json> {
              if constexpr (std::invocable<Encode &, const T &, CSerializationWriteContext &>) {
                  return encode(value, context);
              } else {
                  return encode(value);
              }
          }),
          decoder([decode = std::move(decode)](const std::shared_ptr<CGame> &game, const json &document,
                                               CSerializationReadContext &context) mutable -> CSerializationResult<T> {
              if constexpr (std::invocable<Decode &, const std::shared_ptr<CGame> &, const json &,
                                           CSerializationReadContext &>) {
                  return decode(game, document, context);
              } else {
                  return decode(game, document);
              }
          }) {}

    using CSerializerBase::deserialize;
    using CSerializerBase::serialize;

    CSerializationResult<json> serialize(const std::any &object, CSerializationWriteContext &context) const final {
        auto result = serializationResult([&]() { return encoder(std::any_cast<const T &>(object), context); });
        return result ? std::move(*result) : CSerializationResult<json>(std::unexpected(std::move(result.error())));
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &object,
                                               CSerializationReadContext &context) const final {
        auto call = serializationResult([&]() { return decoder(game, object, context); });
        if (!call) {
            return std::unexpected(std::move(call.error()));
        }
        auto &result = *call;
        if (!result) {
            return std::unexpected(std::move(result.error()));
        }
        return std::any(std::move(*result));
    }

  private:
    Encoder encoder;
    Decoder decoder;
};

template <typename Serialized, typename Deserialized> class CSerializerFunction {
  public:
    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SharedPtr<V>
    static T serialize(V deserialized) {
        return CSerializerFunction<T, std::shared_ptr<CGameObject>>::serialize(deserialized);
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SharedPtr<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized) {
        return std::dynamic_pointer_cast<typename V::element_type>(
            CSerializerFunction<T, std::shared_ptr<CGameObject>>::deserialize(map, serialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SharedPtr<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized, CSerializationReadContext &context) {
        return std::dynamic_pointer_cast<typename V::element_type>(
            CSerializerFunction<T, std::shared_ptr<CGameObject>>::deserialize(map, serialized, context));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SetLike<V>
    static T serialize(V deserialized) {
        return CSerializerFunction<T, std::set<std::shared_ptr<CGameObject>>>::serialize(
            vstd::cast<std::set<std::shared_ptr<CGameObject>>>(deserialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SetLike<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized) {
        return vstd::cast<V>(
            CSerializerFunction<T, std::set<std::shared_ptr<CGameObject>>>::deserialize(map, serialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::SetLike<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized, CSerializationReadContext &context) {
        return vstd::cast<V>(
            CSerializerFunction<T, std::set<std::shared_ptr<CGameObject>>>::deserialize(map, serialized, context));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::MapLike<V>
    static T serialize(V deserialized) {
        return CSerializerFunction<T, std::map<std::string, std::shared_ptr<CGameObject>>>::serialize(
            vstd::cast<std::map<std::string, std::shared_ptr<CGameObject>>>(deserialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::MapLike<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized) {
        return vstd::cast<V>(
            CSerializerFunction<T, std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(map, serialized));
    }

    template <typename T = Serialized, typename V = Deserialized>
        requires fn::MapLike<V>
    static V deserialize(std::shared_ptr<CGame> map, T serialized, CSerializationReadContext &context) {
        return vstd::cast<V>(CSerializerFunction<T, std::map<std::string, std::shared_ptr<CGameObject>>>::deserialize(
            map, serialized, context));
    }
};

// inline this functions
extern std::set<std::shared_ptr<CGameObject>> array_deserialize(const std::shared_ptr<CGame> &map,
                                                                const std::shared_ptr<json> &object);

extern std::shared_ptr<json> array_serialize(const std::set<std::shared_ptr<CGameObject>> &set);

extern std::map<std::string, std::shared_ptr<CGameObject>> map_deserialize(const std::shared_ptr<CGame> &map,
                                                                           const std::shared_ptr<json> &object);

extern std::shared_ptr<json> map_serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &object);

extern std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game,
                                                       const std::shared_ptr<json> &config);

extern std::shared_ptr<CGameObject> object_deserialize(const std::shared_ptr<CGame> &game,
                                                       const std::shared_ptr<json> &config,
                                                       CSerializationReadContext &context);

extern std::shared_ptr<json> object_serialize(const std::shared_ptr<CGameObject> &object);

extern std::set<std::string> array_string_deserialize(std::shared_ptr<CGame> map, std::shared_ptr<json> object);

extern std::shared_ptr<json> array_string_serialize(std::set<std::string> set);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::string &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, const std::shared_ptr<json> &value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, bool value);

extern void add_member(const std::shared_ptr<json> &object, const std::string &key, int value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::string &value);

extern void add_arr_member(const std::shared_ptr<json> &object, const std::shared_ptr<json> &value);

extern void add_arr_member(const std::shared_ptr<json> &object, bool value);

extern void add_arr_member(const std::shared_ptr<json> &object, int value);

extern std::shared_ptr<CSerializerBase> game_object_pointer_serializer();

extern std::shared_ptr<CSerializerBase> game_object_set_serializer();

extern std::shared_ptr<CSerializerBase> game_object_map_serializer();

template <> class CSerializerFunction<std::shared_ptr<json>, std::shared_ptr<CGameObject>> {
  public:
    static std::shared_ptr<json> serialize(const std::shared_ptr<CGameObject> &object);

    static std::shared_ptr<CGameObject> deserialize(const std::shared_ptr<CGame> &map,
                                                    const std::shared_ptr<json> &config);
    static std::shared_ptr<CGameObject> deserialize(const std::shared_ptr<CGame> &map,
                                                    const std::shared_ptr<json> &config,
                                                    CSerializationReadContext &context);
};

template <> class CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>> {
  public:
    static std::shared_ptr<json> serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &object);

    static std::map<std::string, std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                                           const std::shared_ptr<json> &object);
    static std::map<std::string, std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                                           const std::shared_ptr<json> &object,
                                                                           CSerializationReadContext &context);
};

template <> class CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>> {
  public:
    static std::shared_ptr<json> serialize(const std::set<std::shared_ptr<CGameObject>> &set);

    static std::set<std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                              const std::shared_ptr<json> &object);
    static std::set<std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                              const std::shared_ptr<json> &object,
                                                              CSerializationReadContext &context);
};

class CSerialization {
    static std::shared_ptr<const CSerializerBase> serializer(std::type_index type);

    template <typename Deserialized> static std::shared_ptr<const CSerializerBase> serializer() {
        return serializer(std::type_index(typeid(Deserialized)));
    }

    template <typename Context>
    static void completeError(CSerializationError &error, const Context &context, const std::string &fallbackType) {
        if (error.source.empty()) {
            error.source = context.source();
        }
        const auto &path = context.path();
        if (!path.empty() && error.propertyPath != path && !error.propertyPath.starts_with(path + ".") &&
            !error.propertyPath.starts_with(path + "[")) {
            error.propertyPath = path + (error.propertyPath.empty() || error.propertyPath.front() == '[' ? "" : ".") +
                                 error.propertyPath;
        }
        if (error.objectType.empty()) {
            error.objectType = context.objectType().empty() ? fallbackType : context.objectType();
        }
    }

  public:
    template <typename T>
    static CSerializationResult<json> serializeExpected(const T &object, const std::string &source = {}) {
        CSerializationWriteContext context(source);
        return serializeExpected(object, context);
    }

    template <typename T>
    static CSerializationResult<json> serializeExpected(const T &object, CSerializationWriteContext &context) {
        auto codec = serializer<T>();
        if (!codec) {
            CSerializationError error{
                CSerializationErrorCode::MissingCodec, {}, {}, {}, "No JSON codec registered for type"};
            completeError(error, context, typeid(T).name());
            return std::unexpected(std::move(error));
        }
        CSerializationOperation scope(context);
        auto call = serializationResult([&]() {
            auto result = codec->serialize(std::any(object), context);
            if (result && scope.isRoot()) {
                context.finish(*result);
            }
            return result;
        });
        auto result = call ? std::move(*call) : CSerializationResult<json>(std::unexpected(std::move(call.error())));
        if (!result) {
            completeError(result.error(), context, typeid(T).name());
        }
        return result;
    }

    template <typename T>
    static CSerializationResult<T> deserializeExpected(const std::shared_ptr<CGame> &game, const json &document,
                                                       const std::string &source = {}) {
        CSerializationReadContext context(false, source);
        return deserializeExpected<T>(game, document, context);
    }

    template <typename T>
    static CSerializationResult<T> deserializeExpected(const std::shared_ptr<CGame> &game, const json &document,
                                                       CSerializationReadContext &context) {
        auto codec = serializer<T>();
        if (!codec) {
            CSerializationError error{
                CSerializationErrorCode::MissingCodec, {}, {}, {}, "No JSON codec registered for type"};
            completeError(error, context, typeid(T).name());
            return std::unexpected(std::move(error));
        }
        CSerializationOperation scope(context);
        auto call = serializationResult([&]() {
            const auto &payload = context.prepare(game, document);
            auto result = codec->deserialize(game, payload, context);
            if (result && scope.isRoot()) {
                context.finish(game);
            }
            return result;
        });
        auto result =
            call ? std::move(*call) : CSerializationResult<std::any>(std::unexpected(std::move(call.error())));
        if (!result) {
            completeError(result.error(), context, typeid(T).name());
            return std::unexpected(std::move(result.error()));
        }
        auto converted = serializationResult([&]() -> T { return vstd::any_cast<T>(*result); });
        if (!converted) {
            completeError(converted.error(), context, typeid(T).name());
        }
        return converted;
    }

    class StrictScope : public CSerializationReadContext {
      public:
        explicit StrictScope(std::string source = {}) : CSerializationReadContext(true, std::move(source)) {}

        StrictScope(const StrictScope &) = delete;
        StrictScope &operator=(const StrictScope &) = delete;
        StrictScope(StrictScope &&) = delete;
        StrictScope &operator=(StrictScope &&) = delete;
    };

    template <typename Serialized, typename Deserialized> static Serialized serialize(Deserialized deserialized) {
        static_assert(std::same_as<Serialized, json> || std::same_as<Serialized, std::shared_ptr<json>>);
        auto result = serializationValueOrThrow(serializeExpected(deserialized));
        if constexpr (std::same_as<Serialized, json>) {
            return result;
        } else {
            return std::make_shared<json>(std::move(result));
        }
    }

    template <typename Serialized, typename Deserialized>
    static Deserialized deserialize(std::shared_ptr<CGame> map, Serialized serialized) {
        if constexpr (std::same_as<Serialized, json>) {
            return serializationValueOrThrow(deserializeExpected<Deserialized>(map, serialized));
        } else {
            if (!serialized) {
                throw CSerializationException(
                    {CSerializationErrorCode::InvalidInput, {}, {}, {}, "Missing JSON input"});
            }
            return serializationValueOrThrow(deserializeExpected<Deserialized>(map, *serialized));
        }
    }

    static void setProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                            const std::shared_ptr<json> &value);

    static void setProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, const json &value,
                            CSerializationReadContext &context);

    static void setProperty(const std::shared_ptr<json> &conf, const std::string &propertyName,
                            const std::any &propertyValue);

    static void setProperty(const std::shared_ptr<json> &conf, const std::string &propertyName,
                            const std::any &propertyValue, CSerializationWriteContext &context);

    using CoercedStringProperty = std::variant<std::monostate, std::string, int, bool, std::shared_ptr<json>>;

    static CoercedStringProperty coerceStringProperty(std::type_index property, const std::string &value) {
        if (property == std::type_index(typeid(std::string))) {
            return value;
        }
        if (vstd::trim(value).empty()) {
            return std::monostate();
        }

        auto val = vstd::to_int(value);
        if (val.second) {
            return val.first;
        }
        if (value == "true") {
            return true;
        }
        if (value == "false") {
            return false;
        }

        auto parsed = CJsonUtil::from_string(value);
        if (parsed && parsed->is_number() && vstd::str(parsed->get<double>()) != value) {
            return value;
        }
        if (!parsed || parsed->is_string()) {
            return value;
        }
        return parsed;
    }

    static std::string generateName(const std::shared_ptr<CGameObject> &object);

    // Clone contained actors while retaining effect references to actors outside the cloned object.
    static std::shared_ptr<CGameObject> cloneObject(const std::shared_ptr<CGameObject> &object);

    static std::string generateName(const std::shared_ptr<CGameObject> &object,
                                    const std::function<bool(const std::string &)> &isNameTaken);

    // For isolated, serial native fixtures on the loop owner, with no concurrent name generation.
    // Nested scopes restore all name-generator state, including startup guards.
    // Runtime RNGs are deliberately independent; callers save and restore them separately.
    class NameFixtureScopeForTests {
      public:
        explicit NameFixtureScopeForTests(std::optional<std::uint32_t> seed = std::nullopt);
        ~NameFixtureScopeForTests();
        NameFixtureScopeForTests(const NameFixtureScopeForTests &) = delete;
        NameFixtureScopeForTests &operator=(const NameFixtureScopeForTests &) = delete;
        NameFixtureScopeForTests(NameFixtureScopeForTests &&) = delete;
        NameFixtureScopeForTests &operator=(NameFixtureScopeForTests &&) = delete;

      private:
        class State;
        std::unique_ptr<State> previous;
    };

  private:
    friend class CGame;
    friend class CRuntimeBridge;
    static void seedGeneratedNamesForTests(std::uint32_t seed);
    static void markGameSessionStarted();

    static std::type_index getProperty(const std::shared_ptr<CGameObject> &object, const std::string &name);

    static std::type_index getGenericPropertyType(const json *object);

    static void setArrayProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                 const std::string &key, const json &value, CSerializationReadContext &context);

    static void setObjectProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                  const std::string &key, const json &value, CSerializationReadContext &context);

    static void setStringProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                  const std::string &value, CSerializationReadContext &context);

    static void setNumericProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, int value,
                                   CSerializationReadContext &context);

    static void setBooleanProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, bool value,
                                   CSerializationReadContext &context);

    static void setOtherProperty(std::type_index deserializedId, const std::shared_ptr<CGameObject> &object,
                                 const std::string &key, const json &value, CSerializationReadContext &context);

    static bool isString(const std::shared_ptr<CGameObject> &object, const std::string &key);
};
