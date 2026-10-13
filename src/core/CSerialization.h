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

#include <variant>
#include <expected>
#include <stdexcept>

class CGame;

class CGameObject;

class CSerializerBase;

enum class CSerializationErrorCode { MissingCodec, InvalidInput, TypeMismatch, MalformedGraph, CodecFailure };

struct CSerializationError {
    CSerializationErrorCode code;
    std::string source;
    std::string propertyPath;
    std::string objectType;
    std::string message;
};

template <typename T> using CSerializationResult = std::expected<T, CSerializationError>;

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

    virtual CSerializationResult<json> serialize(const std::any &object) const = 0;

    virtual CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &map, const json &object) const = 0;

    // Compatibility bridge while recursive graph loading migrates to explicit borrowed-document contexts.
    virtual CSerializationResult<std::any> deserializeShared(const std::shared_ptr<CGame> &map,
                                                             const std::shared_ptr<json> &object) const {
        if (!object) {
            return std::unexpected(
                CSerializationError{CSerializationErrorCode::InvalidInput, {}, {}, {}, "Missing JSON input"});
        }
        return deserialize(map, *object);
    }
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

template <typename T> class CTypedJsonCodec final : public CSerializerBase {
  public:
    using Encoder = std::function<CSerializationResult<json>(const T &)>;
    using Decoder = std::function<CSerializationResult<T>(const std::shared_ptr<CGame> &, const json &)>;

    CTypedJsonCodec(Encoder encoder, Decoder decoder) : encoder(std::move(encoder)), decoder(std::move(decoder)) {}

    CSerializationResult<json> serialize(const std::any &object) const final {
        auto result = serializationResult([&]() { return encoder(std::any_cast<const T &>(object)); });
        return result ? std::move(*result) : CSerializationResult<json>(std::unexpected(std::move(result.error())));
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &game, const json &object) const final {
        auto call = serializationResult([&]() { return decoder(game, object); });
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
};

template <> class CSerializerFunction<std::shared_ptr<json>, std::map<std::string, std::shared_ptr<CGameObject>>> {
  public:
    static std::shared_ptr<json> serialize(const std::map<std::string, std::shared_ptr<CGameObject>> &object);

    static std::map<std::string, std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                                           const std::shared_ptr<json> &object);
};

template <> class CSerializerFunction<std::shared_ptr<json>, std::set<std::shared_ptr<CGameObject>>> {
  public:
    static std::shared_ptr<json> serialize(const std::set<std::shared_ptr<CGameObject>> &set);

    static std::set<std::shared_ptr<CGameObject>> deserialize(const std::shared_ptr<CGame> &map,
                                                              const std::shared_ptr<json> &object);
};

template <typename Serialized, typename Deserialized> class CSerializer : public CSerializerBase {
  public:
    CSerializationResult<json> serialize(const std::any &object) const final {
        return serializationResult([&]() -> json {
            auto result =
                CSerializerFunction<Serialized, Deserialized>::serialize(vstd::any_cast<Deserialized>(object));
            if constexpr (std::same_as<Serialized, json>) {
                return result;
            } else {
                if (!result) {
                    throw CSerializationException({CSerializationErrorCode::InvalidInput,
                                                   {},
                                                   {},
                                                   {},
                                                   "Legacy codec returned missing JSON output"});
                }
                return *result;
            }
        });
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &map, const json &object) const final {
        return serializationResult([&]() -> std::any {
            if constexpr (std::same_as<Serialized, json>) {
                return CSerializerFunction<Serialized, Deserialized>::deserialize(map, object);
            } else {
                return CSerializerFunction<Serialized, Deserialized>::deserialize(map, std::make_shared<json>(object));
            }
        });
    }
};

template <typename Serialized, typename Deserialized> class CCustomSerializer : public CSerializerBase {
  private:
    std::function<Serialized(Deserialized)> _serialize;
    std::function<Deserialized(std::shared_ptr<CGame>, Serialized)> _deserialize;

  public:
    CCustomSerializer(std::function<Serialized(Deserialized)> _serialize,
                      std::function<Deserialized(std::shared_ptr<CGame>, Serialized)> _deserialize)
        : _serialize(_serialize), _deserialize(_deserialize) {}

    CSerializationResult<json> serialize(const std::any &object) const final {
        return serializationResult([&]() -> json {
            auto result = _serialize(vstd::any_cast<Deserialized>(object));
            if constexpr (std::same_as<Serialized, json>) {
                return result;
            } else {
                if (!result) {
                    throw CSerializationException({CSerializationErrorCode::InvalidInput,
                                                   {},
                                                   {},
                                                   {},
                                                   "Legacy codec returned missing JSON output"});
                }
                return *result;
            }
        });
    }

    CSerializationResult<std::any> deserialize(const std::shared_ptr<CGame> &map, const json &object) const final {
        return serializationResult([&]() -> std::any {
            if constexpr (std::same_as<Serialized, json>) {
                return _deserialize(map, object);
            } else {
                return _deserialize(map, std::make_shared<json>(object));
            }
        });
    }
};

class CSerialization {
    static std::shared_ptr<const CSerializerBase> serializer(std::type_index type);

    template <typename Deserialized> static std::shared_ptr<const CSerializerBase> serializer() {
        return serializer(std::type_index(typeid(Deserialized)));
    }

  public:
    template <typename T>
    static CSerializationResult<json> serializeExpected(const T &object, const std::string &source = {}) {
        auto codec = serializer<T>();
        if (!codec) {
            return std::unexpected(CSerializationError{CSerializationErrorCode::MissingCodec,
                                                       source,
                                                       {},
                                                       typeid(T).name(),
                                                       "No JSON codec registered for type"});
        }
        auto call = serializationResult([&]() { return codec->serialize(std::any(object)); });
        auto result = call ? std::move(*call) : CSerializationResult<json>(std::unexpected(std::move(call.error())));
        if (!result) {
            if (result.error().source.empty()) {
                result.error().source = source;
            }
            if (result.error().objectType.empty()) {
                result.error().objectType = typeid(T).name();
            }
        }
        return result;
    }

    template <typename T>
    static CSerializationResult<T> deserializeExpected(const std::shared_ptr<CGame> &game, const json &document,
                                                       const std::string &source = {}) {
        auto codec = serializer<T>();
        if (!codec) {
            return std::unexpected(CSerializationError{CSerializationErrorCode::MissingCodec,
                                                       source,
                                                       {},
                                                       typeid(T).name(),
                                                       "No JSON codec registered for type"});
        }
        auto call = serializationResult([&]() { return codec->deserialize(game, document); });
        auto result =
            call ? std::move(*call) : CSerializationResult<std::any>(std::unexpected(std::move(call.error())));
        if (!result) {
            if (result.error().source.empty()) {
                result.error().source = source;
            }
            if (result.error().objectType.empty()) {
                result.error().objectType = typeid(T).name();
            }
            return std::unexpected(std::move(result.error()));
        }
        auto converted = serializationResult([&]() -> T { return vstd::any_cast<T>(*result); });
        if (!converted) {
            converted.error().source = source;
            converted.error().objectType = typeid(T).name();
        }
        return converted;
    }

    class StrictScope {
      public:
        StrictScope();

        ~StrictScope();

        StrictScope(const StrictScope &) = delete;
        StrictScope &operator=(const StrictScope &) = delete;
        StrictScope(StrictScope &&) = delete;
        StrictScope &operator=(StrictScope &&) = delete;

      private:
        bool previous;
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

    static void setProperty(const std::shared_ptr<json> &conf, const std::string &propertyName,
                            const std::any &propertyValue);

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

    static bool isStrict();

    static bool setStrict(bool value);

  private:
    static std::type_index getProperty(const std::shared_ptr<CGameObject> &object, const std::string &name);

    static std::type_index getGenericPropertyType(const std::shared_ptr<json> &object);

    static void setArrayProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                 const std::string &key, std::shared_ptr<json> value);

    static void setObjectProperty(const std::shared_ptr<CGameObject> &object, std::type_index property,
                                  const std::string &key, std::shared_ptr<json> value);

    static void setStringProperty(const std::shared_ptr<CGameObject> &object, const std::string &key,
                                  const std::string &value);

    static void setNumericProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, int value);

    static void setBooleanProperty(const std::shared_ptr<CGameObject> &object, const std::string &key, bool value);

    static void setOtherProperty(std::type_index serializedId, std::type_index deserializedId,
                                 const std::shared_ptr<CGameObject> &object, const std::string &key,
                                 const std::any &value);

    static bool isString(const std::shared_ptr<CGameObject> &object, const std::string &key);
};
