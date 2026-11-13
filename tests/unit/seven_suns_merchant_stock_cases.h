// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Included inside the handler test namespace after its shared fixture/helpers.

void testSevenSunsStockExhaustive8000FiniteOutcomesAndInputBounds() {
    // Histogram independently expanded from the reviewed public JSON fixture, not resolver output.
    const std::map<std::string, int> expected{
        {"gold:73", 400},       {"item:AMUL10:1", 400}, {"item:AMUL11:1", 400}, {"item:AMUL12:1", 400},
        {"item:AMUL13:1", 400}, {"item:AROW02:5", 40},  {"item:AROW04:1", 40},  {"item:AROW06:1", 40},
        {"item:AROW07:1", 40},  {"item:AROW08:1", 40},  {"item:AROW09:1", 40},  {"item:AROW11:3", 40},
        {"item:BOLT02:5", 40},  {"item:BOLT03:1", 40},  {"item:BOLT04:1", 40},  {"item:BOLT05:1", 40},
        {"item:BOLT06:3", 40},  {"item:BULL02:5", 40},  {"item:BULL03:3", 40},  {"item:MISC21:1", 400},
        {"item:MISC24:1", 400}, {"item:MISC29:1", 400}, {"item:MISC34:1", 400}, {"item:MISC38:1", 400},
        {"item:MISC40:1", 400}, {"item:MISC42:1", 400}, {"item:MISC43:1", 400}, {"item:POTN03:1", 40},
        {"item:POTN05:1", 40},  {"item:POTN08:1", 80},  {"item:POTN09:1", 40},  {"item:POTN10:1", 40},
        {"item:POTN17:1", 40},  {"item:POTN19:1", 40},  {"item:POTN28:1", 40},  {"item:POTN31:1", 40},
        {"item:POTN37:1", 40},  {"item:POTN43:1", 40},  {"item:POTN44:1", 40},  {"item:SCRL04:1", 40},
        {"item:SCRL06:1", 40},  {"item:SCRL08:1", 40},  {"item:SCRL09:1", 40},  {"item:SCRL16:1", 40},
        {"item:SCRL1B:1", 2},   {"item:SCRL1C:1", 2},   {"item:SCRL1D:1", 42},  {"item:SCRL1E:1", 84},
        {"item:SCRL1F:1", 42},  {"item:SCRL1G:1", 42},  {"item:SCRL1H:1", 42},  {"item:SCRL1I:1", 84},
        {"item:SCRL1J:1", 42},  {"item:SCRL1K:1", 42},  {"item:SCRL1L:1", 42},  {"item:SCRL1M:1", 84},
        {"item:SCRL1N:1", 42},  {"item:SCRL1O:1", 42},  {"item:SCRL1P:1", 42},  {"item:SCRL1Q:1", 42},
        {"item:SCRL1S:1", 84},  {"item:SCRL1T:1", 42},  {"item:SCRL2I:1", 2},   {"item:SCRL66:1", 4},
        {"item:SCRL67:1", 2},   {"item:SCRL68:1", 2},   {"item:SCRL69:1", 2},   {"item:SCRL70:1", 4},
        {"item:SCRL71:1", 2},   {"item:SCRL72:1", 2},   {"item:SCRL73:1", 2},   {"item:SCRL75:1", 2},
        {"item:SCRL76:1", 2},   {"item:SCRL77:1", 2},   {"item:SCRL78:1", 2},   {"item:SCRL79:1", 2},
        {"item:SCRL80:1", 2},   {"item:SCRL81:1", 2},   {"item:SCRL82:1", 2},   {"item:SCRL83:1", 2},
        {"item:SCRL84:1", 2},   {"item:SCRL85:1", 4},   {"item:SCRL86:1", 4},   {"item:SCRL87:1", 4},
        {"item:SCRL89:1", 2},   {"item:SCRL90:1", 2},   {"item:SCRL91:1", 2},   {"item:SCRL92:1", 2},
        {"item:SCRL93:1", 2},   {"item:SCRL94:1", 2},   {"item:SCRL95:1", 2},   {"item:SCRL96:1", 2},
        {"item:SCRL97:1", 2},   {"item:SCRL98:1", 2},   {"item:SCRL99:1", 2},   {"item:WAND03:1", 40},
        {"item:WAND05:1", 40},  {"item:WAND06:1", 40},  {"none", 480}};
    std::map<std::string, int> actual;
    std::array<int, 4> depths{};
    int runs = 0;
    for (int first = 1; first <= 20; ++first)
        for (int second = 1; second <= 20; ++second)
            for (int third = 1; third <= 20; ++third) {
                const std::array<int, 3> draws{first, second, third};
                auto selected = CSevenSunsMerchantStock::resolveRollsForTests(draws);
                const auto &rolls = selected.at("rolls"), &outcome = selected.at("outcome");
                expect_true(rolls.is_array() && !rolls.empty() && rolls.size() <= 3,
                            "finite stock resolution uses one to three real native draws");
                ++depths.at(rolls.size());
                for (std::size_t index = 0; index < rolls.size(); ++index)
                    expect_true(rolls.at(index).at("column").get<int>() == draws[index],
                                "every consumed native column preserves the selected roll");
                auto kind = outcome.at("kind").get<std::string>();
                auto key = kind;
                if (kind == "gold")
                    key += ":" + std::to_string(outcome.at("gold").get<int>());
                else if (kind == "item") {
                    const auto code = outcome.at("code").get<std::string>();
                    expect_true(!code.starts_with("RND") && !code.starts_with("rnd"),
                                "random family names never survive as concrete source items");
                    key += ":" + code + ":" + std::to_string(outcome.at("quantity").get<int>());
                    auto item = std::ranges::find_if(seven_suns_stock::Items,
                                                     [&](const auto &row) { return row.code == code; });
                    expect_true(item != seven_suns_stock::Items.end(),
                                "all source item outcomes have a reviewed concrete native resource");
                    if (item != seven_suns_stock::Items.end())
                        for (std::size_t index = 0; index < 3; ++index)
                            expect_true(outcome.at("charges").at(index).get<int>() == item->charges[index],
                                        "native default item charges survive finite resolution");
                }
                ++actual[key];
                ++runs;
            }
    expect_true(runs == 8000 && actual == expected && depths == std::array<int, 4>{0, 5600, 2280, 120},
                "all8000 actual native resolver triples match independently expanded source outcome multiplicities and "
                "depth bounds");
    for (int invalid : {0, 21, -1}) {
        bool rejected = false;
        try {
            CSevenSunsMerchantStock::resolveRollsForTests({invalid, 1, 1});
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected, "native finite resolver rejects out-of-range first-column authority");
    }
}

void testSevenSunsStockPreparedFourLineagesUseRealWeaponAndConcretePossessions() {
    for (std::size_t index = 0; index < 4; ++index) {
        SevenSunsMerchantFixture f;
        f.focus(index);
        const std::string area = index < 2 ? "AR0601" : "AR0602";
        const auto old = f.protectedActors[index];
        const auto oldItems = old->getAllItems();
        auto prepared = CSevenSunsMerchantStock::prepare(f.game, SevenSunsMerchantFixture::Names[index], area, [] {});
        CSevenSunsMerchantStock::validatePrepared(prepared, f.game, SevenSunsMerchantFixture::Names[index], area,
                                                  [] {});
        auto actor = prepared.actor;
        expect_true(actor && actor != old && actor->getName() == SevenSunsMerchantFixture::Names[index] &&
                        actor->getStringProperty("sourceActor") == SevenSunsMerchantFixture::Sources[index] &&
                        actor->getController() == prepared.controller &&
                        actor->getFightController() == prepared.fightController &&
                        actor->getActions() == std::set<std::shared_ptr<CInteraction>>{prepared.attack} &&
                        prepared.controller->getTarget() == "player" && actor->getHp() == 28 &&
                        actor->getHpMax() == 28 && actor->getStats()->getDmgMin() == 1 &&
                        actor->getStats()->getDmgMax() == 12 && actor->getStats()->getHit() == 75 &&
                        actor->getEquipped().size() == 1 && actor->getWeapon() == prepared.owned.at(0) &&
                        prepared.owned.at(0)->getTypeId() == "citySevenSunsDoppssWeapon" &&
                        prepared.owned.at(0)->getBoolProperty("plugin_cityUndroppable") &&
                        prepared.owned.at(0)->getBoolProperty("plugin_cityUnstealable") &&
                        !prepared.owned.at(0)->getBoolProperty("plugin_cityTradeable") &&
                        old->getAllItems() == oldItems && f.oldOwnershipIntact(index) && f.merchantDestroyed == 0,
                    "actual raw native replacement construction preserves old ownership and creates the reviewed "
                    "body/controllers/slot0 weapon");
        const auto &selected = prepared.receipt.at("outcome");
        expect_true(prepared.owned.size() == (selected.at("kind").get<std::string>() == "item" ? 2 : 1) &&
                        actor->getGold() == selected.at("gold").get<int>() &&
                        actor->getStringProperty("plugin_citySevenSunsStock") ==
                            "city-json:" + prepared.receipt.dump() &&
                        f.map->getObjectByName(SevenSunsMerchantFixture::Names[index]) == old &&
                        f.map->tryBeginSaveSnapshot().has_value(),
                    "initial materialization has actual item/gold/no-item possession and a persisted certificate "
                    "without publishing or retiring the old actor");
        for (const auto &item : prepared.owned)
            expect_true(item && !item->getStringProperty("plugin_citySourceItem").starts_with("RND") &&
                            item->getTypeId().starts_with("citySevenSuns"),
                        "each owned object is a concrete native resource, never an unresolved random placeholder");
    }
}

void testSevenSunsStockPreparedRejectsControllerActionAndInitialMetadataChanges() {
    for (int mode = 0; mode < 8; ++mode) {
        SevenSunsMerchantFixture f;
        auto prepared = CSevenSunsMerchantStock::prepare(f.game, SevenSunsMerchantFixture::Names[0], "AR0601", [] {});
        if (mode == 0)
            prepared.actor->setController(std::make_shared<CController>());
        if (mode == 1)
            prepared.actor->setFightController(std::make_shared<CMonsterFightController>());
        if (mode == 2)
            prepared.actor->setActions({});
        if (mode == 3)
            prepared.controller->setTarget("someoneElse");
        if (mode == 4)
            prepared.attack->setGame(std::make_shared<CGame>());
        if (mode == 5)
            prepared.owned[0]->setNumericProperty("plugin_citySourceEnchantment", 99);
        if (mode == 6)
            prepared.actor->setHp(1);
        if (mode == 7)
            prepared.owned[0]->setStringProperty("plugin_cityCharges", "[0,0,0]");
        bool rejected = false;
        try {
            CSevenSunsMerchantStock::validatePrepared(prepared, f.game, SevenSunsMerchantFixture::Names[0], "AR0601",
                                                      [] {});
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected, "strict prepublication validator rejects controller/action/initial HP/metadata or "
                              "unprefixed charge mutation");
    }
}

void testSevenSunsStockSettledValidationAllowsActualMutableHealthInventoryAndEquipment() {
    SevenSunsMerchantFixture f;
    auto prepared = CSevenSunsMerchantStock::prepare(f.game, SevenSunsMerchantFixture::Names[0], "AR0601", [] {});
    auto actor = prepared.actor;
    const auto receipt = prepared.receipt;
    actor->setHp(1);
    actor->setGold(actor->getGold() + 19);
    for (const auto &item : actor->getItems()) {
        actor->removeItem(item);
        f.player->addItem(item);
    }
    auto weapon = actor->getWeapon();
    actor->setEquipped({});
    f.player->addItem(weapon);
    auto effect = std::make_shared<CEffect>();
    effect->setGame(f.game);
    effect->setCaster(actor);
    effect->setVictim(actor);
    actor->addEffect(effect);
    CSevenSunsMerchantStock::validateSettled(actor, receipt, f.game, SevenSunsMerchantFixture::Names[0], "AR0601",
                                             [] {});
    actor->setHp(0);
    CSevenSunsMerchantStock::validateSettled(actor, receipt, f.game, SevenSunsMerchantFixture::Names[0], "AR0601",
                                             [] {});
    expect_true(actor->getHp() == 0 && actor->getGold() == receipt.at("outcome").at("gold").get<int>() + 19 &&
                    f.player->getAllItems().contains(weapon) && actor->getEffects().contains(effect),
                "settled certificate validation permits legitimate later damage/death/gold/ownership/equipment/effects "
                "without restoring initial stock");
}

void testSevenSunsStockMatchingActorAndClockForgeryCannotPassFiniteReplay() {
    for (int mode = 0; mode < 16; ++mode) {
        SevenSunsMerchantFixture f;
        auto flow = f.beginMerchant();
        SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
        flow.reset();
        f.settle();
        auto actor = f.replacement();
        auto document = f.merchantDocument();
        auto &stock = document["actors"][SevenSunsMerchantFixture::Names[0]]["stock"];
        if (mode == 0)
            stock["version"] = 1.0;
        if (mode == 1)
            stock["native"]["hpMax"] = 28.0;
        if (mode == 2)
            stock["outcome"]["quantity"] = static_cast<double>(stock.at("outcome").at("quantity").get<int>());
        if (mode == 3)
            stock["rolls"][0]["row"] = static_cast<double>(stock.at("rolls").at(0).at("row").get<int>());
        if (mode == 4)
            stock["rolls"][0]["column"] = 4294967297ULL;
        if (mode == 5)
            stock["rolls"][0]["column"] = 21;
        if (mode == 6)
            stock["rolls"][0]["token"] = "RNDTRE05";
        if (mode == 7)
            stock["rolls"][0]["family"] = "unreviewedFamily";
        if (mode == 8)
            stock["rolls"] = json::array();
        if (mode == 9) {
            const json firstRoll = stock.at("rolls").at(0);
            stock["rolls"][stock.at("rolls").size()] = firstRoll;
        }
        if (mode == 10)
            stock["nativeDiceRule"] = "inventedDiceRule";
        if (mode == 11)
            stock["sourceScheduleRaw"] = 0;
        if (mode == 12)
            stock["owned"][0]["resourceId"] = "cityItemS1-12";
        if (mode == 13)
            stock["unexpectedKey"] = true;
        if (mode == 14)
            stock.erase("weaponBaseFingerprint");
        if (mode == 15)
            stock["outcome"]["code"] = "RNDMAG01";
        actor->setStringProperty("plugin_citySevenSunsStock", "city-json:" + stock.dump());
        if (mode < 4) {
            // CJson.dump erases integral double spelling. Test the typed native boundary before encoding.
            bool rejected = false;
            try {
                CSevenSunsMerchantStock::validateSettled(actor, stock, f.game, SevenSunsMerchantFixture::Names[0],
                                                         "AR0601", [] {});
            } catch (const std::exception &) {
                rejected = true;
            }
            expect_true(rejected && f.map->tryBeginSaveSnapshot().has_value(),
                        "typed native stock certificate rejects integral double aliases before lossy JSON encoding");
            continue;
        }
        f.map->setStringProperty(SevenSunsMerchantFixture::MerchantStateKey, "city-json:" + document.dump());
        bool rejected = false;
        try {
            f.settle();
        } catch (const std::exception &) {
            rejected = true;
        }
        expect_true(rejected && !f.map->tryBeginSaveSnapshot().has_value() && f.replacement() == actor &&
                        f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) == actor && f.merchantDestroyed == 0,
                    "matching actor+clock copies cannot forge typed finite stock provenance or reopen save admission");
    }
}

void testSevenSunsStockFailedUnpublishedSelfEffectExpiresWithMapWhileGameLives() {
    std::shared_ptr<CGame> livingGame;
    std::weak_ptr<CMap> oldMap;
    std::weak_ptr<CCreature> candidate;
    std::weak_ptr<CEffect> cycle;
    {
        SevenSunsMerchantFixture f;
        livingGame = f.game;
        oldMap = f.map;
        bool exposed = false;
        auto observer = std::make_shared<CCustomTrigger>(
            std::string(SevenSunsMerchantFixture::Names[0]) + "NativeWeapon", "onEquip", [&](auto, auto event) {
                auto caused = std::dynamic_pointer_cast<CGameEventCaused>(event);
                auto actor = caused ? std::dynamic_pointer_cast<CCreature>(caused->getCause()) : nullptr;
                if (!actor)
                    return;
                auto effect = std::make_shared<CEffect>();
                effect->setGame(f.game);
                effect->setCaster(actor);
                effect->setVictim(actor);
                actor->addEffect(effect);
                candidate = actor;
                cycle = effect;
                exposed = true;
            });
        f.map->getEventHandler()->registerTrigger(observer);
        bool rejected = false;
        try {
            CSevenSunsMerchantStock::prepare(f.game, SevenSunsMerchantFixture::Names[0], "AR0601", [&] {
                if (exposed)
                    throw std::runtime_error("stock equip continuation failed");
            });
        } catch (const std::runtime_error &error) {
            rejected = std::string(error.what()) == "stock equip continuation failed";
        }
        expect_true(rejected && exposed && !candidate.expired() && !cycle.expired() &&
                        !f.map->tryBeginSaveSnapshot().has_value() &&
                        f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) == f.protectedActors[0] &&
                        f.merchantDestroyed == 0,
                    "failed real equip exposure retains its unpublished self-cycle and quarantines without touching "
                    "the old owner");
        auto destination = std::make_shared<CMap>();
        destination->setGame(livingGame);
        livingGame->setMap(destination);
    }
    vstd::event_loop<>::instance()->runReady();
    expect_true(livingGame->getContext()->isActive() && oldMap.expired() && candidate.expired() && cycle.expired(),
                "staged lifetime anchor breaks failed unpublished actor/effect cycles through map destruction without "
                "explicit cleanup or game shutdown");
}

void testSevenSunsStockStagedLifetimeRespectsRealForeignMapAdoption() {
    std::shared_ptr<CGame> livingGame;
    std::shared_ptr<CMap> adoptedMap;
    std::weak_ptr<CMap> sourceMap;
    std::weak_ptr<CCreature> adopted;
    std::weak_ptr<CEffect> effectAlias;
    {
        SevenSunsMerchantFixture f;
        livingGame = f.game;
        sourceMap = f.map;
        auto prepared = CSevenSunsMerchantStock::prepare(f.game, SevenSunsMerchantFixture::Names[0], "AR0601", [] {});
        auto effect = std::make_shared<CEffect>();
        effect->setGame(f.game);
        effect->setCaster(prepared.actor);
        effect->setVictim(prepared.actor);
        prepared.actor->addEffect(effect);
        adopted = prepared.actor;
        effectAlias = effect;
        adoptedMap = std::make_shared<CMap>();
        adoptedMap->setGame(livingGame);
        livingGame->setMap(adoptedMap);
        adoptedMap->addObject(prepared.actor);
    }
    vstd::event_loop<>::instance()->runReady();
    expect_true(sourceMap.expired() && !adopted.expired() && !effectAlias.expired() &&
                    adoptedMap->getObjectByName(SevenSunsMerchantFixture::Names[0]) == adopted.lock() &&
                    adopted.lock()->getEffects().contains(effectAlias.lock()),
                "old staged-owner map teardown leaves an actually adopted current actor and its self-effect intact");
    auto destination = std::make_shared<CMap>();
    destination->setGame(livingGame);
    livingGame->setMap(destination);
    adoptedMap.reset();
    vstd::event_loop<>::instance()->runReady();
    expect_true(adopted.expired() && effectAlias.expired() && livingGame->getContext()->isActive(),
                "the adopting map eventually owns normal cycle cleanup while the original game remains alive");
}

void testSevenSunsStockNaturalReplacementActualDefeatAwards420ExactlyOnce() {
    SevenSunsMerchantFixture f;
    f.map->setBoolProperty("plugin_cityFixedLoot", true);
    const int before = f.player->getExp();
    auto flow = f.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    f.settle();
    auto defeated = f.replacement();
    auto weapon = defeated->getWeapon();
    expect_true(f.player->getExp() == before && f.merchantDestroyed == 0,
                "quiet original replacement gives no combat XP or old death credit");
    defeated->setHp(0);
    CFightHandler::defeatedCreature(f.player, defeated);
    expect_true(f.player->getExp() == before + 420 && f.newDestroyed == 1 && f.merchantDestroyed == 0 &&
                    !f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) && defeated->getWeapon() == weapon &&
                    !f.player->getAllItems().contains(weapon) && f.map->tryBeginSaveSnapshot().has_value(),
                "real certified new-actor defeat grants exact420 once and retains its undroppable natural weapon");
    CFightHandler::defeatedCreature(f.player, defeated);
    expect_true(f.player->getExp() == before + 420 && f.newDestroyed == 1 && f.oldOwnershipIntact(),
                "repeat actual defeat cannot grant a second420 or kill the retained old merchant");
    SevenSunsMerchantFixture ordinary;
    ordinary.map->setBoolProperty("plugin_cityFixedLoot", true);
    auto enemy = ordinary.protectedActors[4];
    const int original = ordinary.player->getExp();
    const int expected = static_cast<int>(250 * std::pow(2.0, enemy->getScale() - ordinary.player->getLevel()));
    enemy->setHp(0);
    CFightHandler::defeatedCreature(ordinary.player, enemy);
    expect_true(ordinary.player->getExp() == original + expected && expected != 420,
                "ordinary nonreplacement defeat keeps the existing scale-based XP policy");
}

void testSevenSunsStockForgedDedicatedDefeatCannotFallBackToGenericXp() {
    SevenSunsMerchantFixture f;
    f.map->setBoolProperty("plugin_cityFixedLoot", true);
    auto flow = f.beginMerchant();
    SevenSunsMerchantFixture::finish(*flow, {1, 5, 11, 12});
    flow.reset();
    f.settle();
    auto defeated = f.replacement();
    const int before = f.player->getExp();
    defeated->setStringProperty("plugin_citySevenSunsStock", "city-json:{}");
    defeated->setHp(0);
    bool rejected = false;
    try {
        CFightHandler::defeatedCreature(f.player, defeated);
    } catch (const std::exception &) {
        rejected = true;
    }
    expect_true(rejected && f.player->getExp() == before &&
                    f.map->getObjectByName(SevenSunsMerchantFixture::Names[0]) == defeated && f.newDestroyed == 0 &&
                    f.merchantDestroyed == 0 && !f.map->tryBeginSaveSnapshot().has_value(),
                "a malformed dedicated role fails inside the actual defeat boundary without generic XP fallback or "
                "accepted partial recovery");
}
