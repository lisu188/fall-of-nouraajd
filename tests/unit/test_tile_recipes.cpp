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
#include "core/CLoader.h"
#include "core/CPythonOverrides.h"
#include "core/CWrapper.h"
#include "core/CSerialization.h"
#include "core/CTypes.h"
#include "handler/CObjectHandler.h"
#include "object/CTile.h"
#include "test_harness.h"
#include "veventloop.h"

#include <iostream>
#include <memory>
#include <random>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace {

json tileConfig(std::string label = "Ground", bool can_step = true) {
    return {{"class", "CTile"},
            {"properties",
             {{"animation", "images/tiles/ground"},
              {"canStep", can_step},
              {"description", "A floor"},
              {"label", label},
              {"movementCost", 3},
              {"posx", 2},
              {"posy", 3},
              {"posz", -1},
              {"tileType", "ground"}}}};
}

struct Fixture {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    std::shared_ptr<CObjectHandler> handler = game->getObjectHandler();

    Fixture() {
        handler->registerNativeType("CTile", [] { return std::make_shared<CTile>(); });
    }

    void configure(const std::string &id, const json &document) {
        handler->registerConfig(id, std::make_shared<const json>(document));
    }
    std::shared_ptr<CTile> create(const std::string &id) { return handler->createObject<CTile>(game, id); }
};

class RestoreRng {
  public:
    ~RestoreRng() { vstd::rng() = previous; }

  private:
    std::mt19937_64 previous = vstd::rng();
};

bool sameTileProperties(const std::shared_ptr<CTile> &first, const std::shared_ptr<CTile> &second) {
    return first && second && first->getAnimation() == second->getAnimation() &&
           first->getLabel() == second->getLabel() && first->getDescription() == second->getDescription() &&
           first->canStep() == second->canStep() && first->getMovementCost() == second->getMovementCost() &&
           first->getCoords() == second->getCoords() && first->getTileType() == second->getTileType() &&
           first->getType() == second->getType() && first->getTypeId() == second->getTypeId();
}

void testRecipePropertiesIdentityAndRngMatchRegularCodec() {
    Fixture fixture;
    fixture.configure("GroundTile", tileConfig());
    RestoreRng restore_rng;
    const auto before_rng = vstd::rng();
    std::shared_ptr<CTile> cached;
    {
        CSerialization::NameFixtureScopeForTests names(401);
        cached = fixture.create("GroundTile");
    }
    const auto after_cached_rng = vstd::rng();
    vstd::rng() = before_rng;
    std::shared_ptr<CTile> regular;
    {
        CSerialization::NameFixtureScopeForTests names(401);
        // A value copy has no cached document identity and exercises the ordinary property codec.
        auto document = tileConfig();
        CSerializationReadContext context(true, "tileRecipeBaseline");
        regular = std::dynamic_pointer_cast<CTile>(serializationValueOrThrow(
            CSerialization::deserializeExpected<std::shared_ptr<CGameObject>>(fixture.game, document, context)));
        regular->setTypeId("GroundTile");
    }
    expect_true(sameTileProperties(cached, regular), "compiled tile properties match the regular strict codec");
    expect_true(cached->getName() == regular->getName() && vstd::rng() == after_cached_rng,
                "recipe compilation must preserve generated names and gameplay RNG consumption");
    auto second = fixture.create("GroundTile");
    expect_true(second != cached && second->getName() != cached->getName() && second->getGame() == fixture.game,
                "recipe reuse must construct independent objects with individual names and game ownership");
    cached->setStringProperty("label", "changed");
    cached->setNumericProperty("runtimeValue", 11);
    cached->setCanStep(false);
    cached->setMovementCost(12);
    expect_true(second->getLabel() == "Ground" && !second->hasProperty("runtimeValue") && second->canStep() &&
                    second->getMovementCost() == 3 && fixture.create("GroundTile")->getLabel() == "Ground",
                "mutating one tile must not change another tile or the immutable construction recipe");
    auto defaults = json{{"class", "CTile"}, {"properties", json::object()}};
    fixture.configure("defaultTile", defaults);
    auto default_tile = fixture.create("defaultTile");
    expect_true(default_tile && !default_tile->canStep() && default_tile->getMovementCost() == 1 &&
                    default_tile->getTileType().empty() && default_tile->getCoords() == Coords(0, 0, 0),
                "an empty compiled recipe preserves native constructor defaults");
    auto identity = tileConfig();
    identity["properties"]["name"] = "authoredTile";
    identity["properties"]["type"] = "authoredType";
    identity["properties"]["typeId"] = "ignoredConfiguredType";
    fixture.configure("identityTile", identity);
    auto authored = fixture.create("identityTile");
    expect_true(authored && authored->getName() == "authoredTile" && authored->getType() == "authoredType" &&
                    authored->getTypeId() == "identityTile",
                "compiled identity properties preserve authored overrides and the outer configured type id");
}

class NotificationProbe : public CGameObject {
    V_META(NotificationProbe, CGameObject,
           V_METHOD(NotificationProbe, onPropertiesChanged, void, std::set<std::string>),
           V_METHOD(NotificationProbe, onPropertyChanged, void, std::string))

  public:
    void onPropertiesChanged(std::set<std::string> names) { batches.push_back(std::move(names)); }
    void onPropertyChanged(std::string) { ++individualChanges; }
    std::vector<std::set<std::string>> batches;
    std::size_t individualChanges = 0;
};

void testNativeGameplayRegistrationActuallyReusesRecipes() {
    auto game = CGameLoader::loadGame();
    auto handler = game->getObjectHandler();
    const auto before = handler->getTileRecipeDiagnostics();
    auto ground = handler->createObject<CTile>(game, "GroundTile");
    auto mountain = handler->createObject<CTile>(game, "MountainTile");
    auto second_ground = handler->createObject<CTile>(game, "GroundTile");
    const auto after = handler->getTileRecipeDiagnostics();
    expect_true(ground && mountain && second_ground && ground->canStep() && !mountain->canStep() &&
                    ground->getTileType() == "ground" && mountain->getTileType() == "mountain" &&
                    ground != second_ground && after.applications - before.applications == 3 &&
                    after.compilations - before.compilations <= 2,
                "the actual loader and native gameplay registry must reuse ground and mountain recipes");
}

void testNativeWrapperPreservesPythonFallback() {
    auto game = std::make_shared<CGame>();
    auto handler = game->getObjectHandler();
    handler->registerNativeType("CTile", [] { return std::make_shared<CWrapper<CTile>>(); });
    handler->registerConfig("nativeWrapper", std::make_shared<const json>(tileConfig()));
    auto native = handler->createObject<CTile>(game, "nativeWrapper");
    expect_true(native && native->getLabel() == "Ground" && handler->getTileRecipeDiagnostics().applications == 1,
                "an exact native tile wrapper may reuse a compiled scalar recipe");

    auto python_game = std::make_shared<CGame>();
    auto python_handler = python_game->getObjectHandler();
    auto retained = std::make_shared<CWrapper<CTile>>();
    CPythonOverrides::retain(retained, pybind11::dict());
    python_handler->registerNativeType("CTile", [retained] { return retained; });
    python_handler->registerConfig("pythonWrapper", std::make_shared<const json>(tileConfig()));
    auto python_tile = python_handler->createObject<CTile>(python_game, "pythonWrapper");
    expect_true(python_tile && python_tile->getLabel() == "Ground" &&
                    python_handler->getTileRecipeDiagnostics().applications == 0,
                "a wrapper retained by Python always keeps ordinary property dispatch");
    CPythonOverrides::release(retained.get());
}

void testRecipeRetainsPropertyNotificationBatch() {
    auto game = std::make_shared<CGame>();
    auto handler = game->getObjectHandler();
    auto probe = std::make_shared<NotificationProbe>();
    handler->registerNativeType("CTile", [probe] {
        auto tile = std::make_shared<CTile>();
        tile->connect("propertiesChanged", probe, "onPropertiesChanged");
        tile->connect("propertyChanged", probe, "onPropertyChanged");
        return tile;
    });
    auto document = tileConfig();
    handler->registerConfig("observedTile", std::make_shared<const json>(document));
    auto tile = handler->createObject<CTile>(game, "observedTile");
    vstd::event_loop<>::instance()->runUntilIdle();
    std::set<std::string> expected;
    for (const auto &[key, value] : document["properties"].items()) {
        static_cast<void>(value);
        expected.insert(key);
    }
    expect_true(tile && probe->batches == std::vector<std::set<std::string>>{expected} && probe->individualChanges == 0,
                "compiled tile creation emits one identical property notification batch");
    expect_true(handler->getTileRecipeDiagnostics().applications == 1,
                "notification parity must exercise the actual compiled creation path");
}

void testRecipeInvalidationAndRegistrationRollback() {
    Fixture fixture;
    fixture.configure("terrain", tileConfig("original"));
    expect_true(fixture.create("terrain")->getLabel() == "original", "initial recipe uses the registered config");
    const auto before = fixture.handler->getTileRecipeDiagnostics();
    {
        CObjectHandler::RegistrationTransaction outer(fixture.handler);
        fixture.configure("terrain", tileConfig("temporary", false));
        auto temporary = fixture.create("terrain");
        expect_true(temporary->getLabel() == "temporary" && !temporary->canStep(),
                    "config replacement invalidates the previous compiled recipe");
        {
            CObjectHandler::RegistrationTransaction inner(fixture.handler);
            fixture.configure("terrain", tileConfig("nested"));
            expect_true(fixture.create("terrain")->getLabel() == "nested", "nested transaction compiles its config");
        }
        expect_true(fixture.create("terrain")->getLabel() == "temporary",
                    "failed nested registration restores its parent's compiled values");
    }
    expect_true(fixture.create("terrain")->getLabel() == "original",
                "failed outer registration restores the original recipe without stale values");
    auto after = fixture.handler->getTileRecipeDiagnostics();
    expect_true(after.compilations - before.compilations == 4 && after.invalidations - before.invalidations == 4,
                "each replaced or rolled-back generation is compiled once and invalidates the prior recipe");
    {
        CObjectHandler::RegistrationTransaction outer(fixture.handler);
        fixture.configure("terrain", tileConfig("superseded"));
        {
            CObjectHandler::RegistrationTransaction inner(fixture.handler);
            fixture.configure("terrain", tileConfig("committed"));
            expect_true(inner.commit(), "nested recipe registration transaction can commit");
        }
    }
    expect_true(fixture.create("terrain")->getLabel() == "committed",
                "a superseded outer rollback cannot invalidate a newer committed registration");
    fixture.handler->unregisterConfig("terrain");
    expect_true(!fixture.create("terrain"), "unregistering terrain cannot reuse a stale recipe");
    fixture.configure("terrain", tileConfig("replacement"));
    expect_true(fixture.create("terrain")->getLabel() == "replacement",
                "registering terrain after removal uses its new immutable document");
}

class ConstructorProbeTile : public CTile {
    V_META(ConstructorProbeTile, CTile, V_METHOD(ConstructorProbeTile, initialize))

  public:
    void initialize() { ++initializations; }
    int initializations = 0;
};

void testConstructorRegistrationRollbackInvalidatesRecipes() {
    auto game = std::make_shared<CGame>();
    auto handler = game->getObjectHandler();
    handler->beginMapScriptScope();
    handler->registerNativeType("CTile", [] { return std::make_shared<CTile>(); });
    handler->registerConfig("scopedTile", std::make_shared<const json>(tileConfig()));
    auto original = handler->createObject<CTile>(game, "scopedTile");
    const auto before = handler->getTileRecipeDiagnostics();
    {
        CObjectHandler::RegistrationTransaction transaction(handler);
        handler->registerType("CTile", [] { return std::make_shared<ConstructorProbeTile>(); });
        auto changed = handler->createObject<ConstructorProbeTile>(game, "scopedTile");
        expect_true(changed && changed->initializations == 1 &&
                        handler->getTileRecipeDiagnostics().applications == before.applications,
                    "replacing a map-scoped native constructor disables its compiled recipe");
    }
    auto restored = handler->createObject<CTile>(game, "scopedTile");
    const auto after = handler->getTileRecipeDiagnostics();
    expect_true(original && restored && typeid(*restored) == typeid(CTile) && restored->getLabel() == "Ground" &&
                    after.compilations == before.compilations + 1 && after.applications == before.applications + 1 &&
                    after.invalidations == before.invalidations + 1,
                "constructor rollback restores native trust and recompiles the restored config generation");
    handler->endMapScriptScope();
}

void testCustomConstructorsAndUnsupportedPropertiesUseRegularCodec() {
    for (const bool native_registration : {false, true}) {
        auto game = std::make_shared<CGame>();
        auto handler = game->getObjectHandler();
        int constructions = 0;
        auto factory = [&constructions]() -> std::shared_ptr<CGameObject> {
            ++constructions;
            return std::make_shared<ConstructorProbeTile>();
        };
        if (native_registration)
            handler->registerNativeType("CTile", factory);
        else
            handler->registerType("CTile", factory);
        handler->registerConfig("customTile", std::make_shared<const json>(tileConfig()));
        auto first = handler->createObject<ConstructorProbeTile>(game, "customTile");
        auto second = handler->createObject<ConstructorProbeTile>(game, "customTile");
        expect_true(first && second && constructions == 2 && first->initializations == 1 &&
                        second->initializations == 1 && first->getLabel() == "Ground" &&
                        handler->getTileRecipeDiagnostics().applications == 0,
                    "custom constructors, derived metadata and initialize methods retain regular codec behavior");
    }
    for (const auto &[key, value] :
         std::vector<std::pair<std::string, json>>{{"label", 7}, {"movementCost", "4"}, {"runtimeValue", 17}}) {
        Fixture fixture;
        auto document = tileConfig();
        document["properties"][key] = value;
        fixture.configure("fallbackTile", document);
        auto tile = fixture.create("fallbackTile");
        expect_true(tile && tile->canStep() && tile->getAnimation() == "images/tiles/ground" &&
                        fixture.handler->getTileRecipeDiagnostics().applications == 0,
                    "a late ineligible property keeps the complete document on normal property dispatch");
        if (key == "label")
            expect_true(tile->getLabel() == "7", "numeric input for a string property retains normal coercion");
        else if (key == "movementCost")
            expect_true(tile->getMovementCost() == 4, "string input for an integer property retains normal coercion");
        else
            expect_true(tile->getNumericProperty(key) == 17, "an unknown scalar property retains dynamic metadata");
    }
    Fixture fixture;
    auto document = tileConfig();
    document["properties"]["canStep"] = "false";
    document["properties"]["movementCost"] = "0";
    document["properties"]["runtimeValue"] = 17;
    document["properties"]["nestedTile"] = {{"class", "CTile"}, {"properties", {{"canStep", true}}}};
    fixture.configure("coercedTile", document);
    auto first = fixture.create("coercedTile");
    auto second = fixture.create("coercedTile");
    auto nested_first = first->getObjectProperty<CTile>("nestedTile");
    auto nested_second = second->getObjectProperty<CTile>("nestedTile");
    expect_true(first && second && !first->canStep() && first->getMovementCost() == 1 &&
                    first->getNumericProperty("runtimeValue") == 17 && nested_first && nested_second &&
                    nested_first != nested_second && nested_first->canStep() &&
                    fixture.handler->getTileRecipeDiagnostics().applications == 0,
                "coercions, dynamic properties and object-valued properties remain on the regular codec");
    fixture.configure("GroundTile", tileConfig());
    fixture.configure("aliasTile", {{"ref", "GroundTile"}, {"properties", {{"label", "alias"}}}});
    auto alias = fixture.create("aliasTile");
    expect_true(alias && alias->getLabel() == "alias" && alias->getTypeId() == "aliasTile" && alias->canStep(),
                "configured references keep their property overlay and final configured type identity");
}

void testStrictFailuresAndRegisteredCodecArePreserved() {
    Fixture fixture;
    auto malformed = tileConfig();
    malformed["properties"]["movementCost"] = json::array({1, 2});
    fixture.configure("malformedTile", malformed);
    bool strict_failure = false;
    try {
        CSerializationReadContext context(true, "strictTileRecipe");
        fixture.handler->createObject<CTile>(fixture.game, "malformedTile", context);
    } catch (const CSerializationException &exception) {
        strict_failure =
            exception.getError().source == "strictTileRecipe" && exception.getError().propertyPath == "movementCost";
    }
    expect_true(strict_failure, "ineligible malformed properties retain strict codec errors and property paths");
    auto permissive = fixture.create("malformedTile");
    expect_true(permissive && permissive->getMovementCost() == 1 && permissive->getLabel() == "Ground",
                "ineligible malformed properties retain permissive skipping and subsequent valid properties");
    for (const auto *field : {"effectReferences", "effectGraph"}) {
        auto graph_document = tileConfig();
        graph_document[field] = {{"invalid", true}};
        fixture.configure("invalidGraphTile", graph_document);
        bool graph_failure = false;
        try {
            CSerializationReadContext context(true, "tileRecipeGraph");
            fixture.handler->createObject<CTile>(fixture.game, "invalidGraphTile", context);
        } catch (const CSerializationException &) {
            graph_failure = true;
        }
        expect_true(graph_failure, "effect graph fields retain ordinary structural and actor-link validation");
    }
    fixture.configure("GroundTile", tileConfig());
    auto previous = CTypes::findCodec(typeid(std::shared_ptr<CGameObject>));
    int codec_calls = 0;
    CTypes::registerJsonCodec<std::shared_ptr<CGameObject>>(
        [](const auto &) -> CSerializationResult<json> { return json::object(); },
        [&codec_calls](const std::shared_ptr<CGame> &,
                       const json &) -> CSerializationResult<std::shared_ptr<CGameObject>> {
            ++codec_calls;
            return std::unexpected(
                CSerializationError{CSerializationErrorCode::InvalidInput, {}, {}, {}, "registered codec rejection"});
        });
    bool codec_failure = false;
    try {
        fixture.create("GroundTile");
    } catch (const CSerializationException &exception) {
        codec_failure = exception.getError().message == "registered codec rejection";
    }
    CTypes::registerCodec(typeid(std::shared_ptr<CGameObject>), previous);
    expect_true(codec_failure && codec_calls == 1,
                "recipe preparation never bypasses the currently registered typed object codec");
}

void testRecipeCompilationWorkIsBounded() {
    Fixture fixture;
    constexpr std::size_t tile_count = 256;
    fixture.configure("GroundTile", tileConfig());
    fixture.configure("MountainTile", tileConfig("Mountain", false));
    const auto before = fixture.handler->getTileRecipeDiagnostics();
    std::set<const CTile *> identities;
    std::vector<std::shared_ptr<CTile>> tiles;
    tiles.reserve(tile_count);
    for (std::size_t index = 0; index < tile_count; ++index) {
        auto tile = fixture.create(index % 2 ? "GroundTile" : "MountainTile");
        expect_true(tile && tile->canStep() == (index % 2 != 0),
                    "bounded recipe guard preserves floor and wall values");
        identities.insert(tile.get());
        tiles.push_back(std::move(tile));
    }
    const auto after = fixture.handler->getTileRecipeDiagnostics();
    const auto compilations = after.compilations - before.compilations;
    const auto applications = after.applications - before.applications;
    std::cout << "[performance] tile recipes objects=" << tile_count << " compilations=" << compilations
              << " budget=2 applications=" << applications << " independent=" << identities.size() << '\n';
    expect_true(compilations == 2 && applications == tile_count && identities.size() == tile_count,
                "one immutable recipe per terrain document must serve every independently constructed tile");
    fixture.configure("GroundTile", tileConfig("reloaded"));
    const auto revision_before = fixture.handler->getTileRecipeDiagnostics();
    for (int index = 0; index < 16; ++index)
        expect_true(fixture.create("GroundTile")->getLabel() == "reloaded", "reloaded recipe uses current properties");
    const auto revision_after = fixture.handler->getTileRecipeDiagnostics();
    expect_true(revision_after.compilations - revision_before.compilations == 1 &&
                    revision_after.applications - revision_before.applications == 16 &&
                    revision_after.invalidations - revision_before.invalidations == 1,
                "a changed config generation recompiles once and then resumes recipe reuse");
}

} // namespace

void run_tile_recipe_tests() {
    testRecipePropertiesIdentityAndRngMatchRegularCodec();
    testNativeGameplayRegistrationActuallyReusesRecipes();
    testNativeWrapperPreservesPythonFallback();
    testRecipeRetainsPropertyNotificationBatch();
    testRecipeInvalidationAndRegistrationRollback();
    testConstructorRegistrationRollbackInvalidatesRecipes();
    testCustomConstructorsAndUnsupportedPropertiesUseRegularCodec();
    testStrictFailuresAndRegisteredCodecArePreserved();
    testRecipeCompilationWorkIsBounded();
}

void run_tile_recipe_performance_tests() { testRecipeCompilationWorkIsBounded(); }
