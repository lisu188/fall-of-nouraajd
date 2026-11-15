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

#include "core/CGame.h"
#include "core/CTypeRegistration.h"
#include "core/CGameplayTypeTable.h"
#include "core/CTypes.h"
#include "core/CWrapper.h"
#include "handler/CObjectHandler.h"
#include "object/CPlayer.h"
#include "test_harness.h"

#include <pybind11/embed.h>

#include <memory>
#include <set>

namespace {

struct RegistrationBaseOne : CGameObject {};
struct RegistrationBaseTwo : RegistrationBaseOne {};
struct RegistrationBaseThree : RegistrationBaseTwo {};

struct RegistrationLeaf : RegistrationBaseThree {
    struct Metadata {
        std::string name() const { return "RegistrationLeaf"; }
    };

    inline static int metadataCalls = 0;

    static const Metadata *static_meta() {
        ++metadataCalls;
        static Metadata metadata;
        return &metadata;
    }
};

struct RegistrationNeedsArgument : CGameObject {
    explicit RegistrationNeedsArgument(int) {}
};

struct RegistrationAbstract : CGameObject {
    virtual void abstractOperation() = 0;
};

template <typename T> concept CanRegisterBuilder = requires { CTypes::register_builder<T>(); };

template <typename T, typename... Bases>
concept CanRegisterType = requires { CTypes::register_type<T, Bases...>(); };

template <typename T, typename... Bases>
concept CanRegisterMetadata = requires { CTypes::register_type_metadata<T, Bases...>(); };

static_assert(CanRegisterBuilder<RegistrationLeaf>);
static_assert(!CanRegisterBuilder<RegistrationNeedsArgument>);
static_assert(!CanRegisterBuilder<RegistrationAbstract>);
static_assert(!CanRegisterBuilder<const RegistrationLeaf>);
static_assert(CanRegisterType<RegistrationLeaf>);
static_assert(CanRegisterType<RegistrationLeaf, RegistrationBaseThree, RegistrationBaseTwo, RegistrationBaseOne,
                              CGameObject>);
static_assert(!CanRegisterType<RegistrationNeedsArgument>);
static_assert(!CanRegisterType<RegistrationAbstract, CGameObject>);
static_assert(!CanRegisterType<RegistrationLeaf, RegistrationLeaf>);
static_assert(!CanRegisterType<RegistrationLeaf, RegistrationBaseOne, CPlayer>);
static_assert(CanRegisterMetadata<RegistrationAbstract, CGameObject>);
static_assert(CanRegisterMetadata<RegistrationNeedsArgument, CGameObject>);
static_assert(!CanRegisterMetadata<RegistrationLeaf, RegistrationLeaf>);
static_assert(!CanRegisterMetadata<RegistrationLeaf, RegistrationBaseOne, CPlayer>);

void testRegistrationInitializesOnceAndPreservesEveryBase() {
    RegistrationLeaf::metadataCalls = 0;
    CTypes::register_type<RegistrationLeaf, RegistrationBaseThree, RegistrationBaseTwo, RegistrationBaseOne,
                          CGameObject>();
    expect_true(RegistrationLeaf::metadataCalls == 1, "a four-base registration initializes its builder only once");

    auto object = std::make_shared<RegistrationLeaf>();
    const auto checkBase = [&]<typename Base>() {
        auto base = vstd::any_cast<std::shared_ptr<Base>>(std::any(object));
        expect_true(base == object, "registration preserves conversion to each base");
        expect_true(vstd::any_cast<std::shared_ptr<RegistrationLeaf>>(std::any(base)) == object,
                    "registration preserves conversion from each base");
        std::set<std::shared_ptr<RegistrationLeaf>> objects{object};
        auto baseSet = vstd::any_cast<std::set<std::shared_ptr<Base>>>(std::any(objects));
        expect_true(baseSet.size() == 1 && *baseSet.begin() == object,
                    "registration preserves collection conversions to every base");
    };
    checkBase.template operator()<RegistrationBaseThree>();
    checkBase.template operator()<RegistrationBaseTwo>();
    checkBase.template operator()<RegistrationBaseOne>();
    checkBase.template operator()<CGameObject>();

    CTypes::register_type_metadata<RegistrationAbstract, CGameObject>();
    CTypes::register_type_metadata<RegistrationNeedsArgument, CGameObject>();
    expect_true(CTypes::findCodec(typeid(std::shared_ptr<RegistrationAbstract>)) != nullptr &&
                    CTypes::findCodec(typeid(std::shared_ptr<RegistrationNeedsArgument>)) != nullptr,
                "metadata registration remains available without default construction");
}

void test_types_are_not_constructible_without_factory_registration() {
    auto game = std::make_shared<CGame>();
    expect_true(game->getObjectHandler()->getType("CPlayer") == nullptr,
                "gameplay metadata alone must not register per-game object factories");
}

void test_gameplay_type_table_registration() {
    auto game = std::make_shared<CGame>();
    type_registration::registerGameplayTypes(game);

    auto handler = game->getObjectHandler();
    std::set<std::string> wrapperNames;
#define FN_CHECK_TYPE(T, ...)                                                                                          \
    expect_true(handler->getType(#T) != nullptr, #T " from the gameplay type table must be constructible");
#define FN_CHECK_WRAPPED(T, ...)                                                                                       \
    FN_CHECK_TYPE(T)                                                                                                   \
    expect_true(wrapperNames.insert(CWrapper<T>::static_meta()->name()).second,                                        \
                "CWrapper<" #T "> must have a unique reflected type name");                                            \
    expect_true(handler->getType(CWrapper<T>::static_meta()->name()) != nullptr,                                       \
                "CWrapper<" #T "> must be registered for the scripted base " #T);
    FN_GAMEPLAY_TYPES(FN_CHECK_TYPE, FN_CHECK_WRAPPED)
#undef FN_CHECK_WRAPPED
#undef FN_CHECK_TYPE

    expect_true(handler->getType("CWrapper<CItem>") == nullptr,
                "plain table rows must not grow scripting trampolines (negative control)");

    auto player = handler->getType("CPlayer");
    expect_true(player != nullptr && player->meta()->inherits("CCreature"),
                "CPlayer metadata must declare its CCreature base chain");
}

} // namespace

int main() {
    pybind11::scoped_interpreter guard{};
    test_types_are_not_constructible_without_factory_registration();
    test_gameplay_type_table_registration();
    testRegistrationInitializesOnceAndPreservesEveryBase();
    return finish_tests();
}
