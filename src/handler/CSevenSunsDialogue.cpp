// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#include "handler/CSevenSunsDialogue.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CPythonOverrides.h"
#include "core/CSceneManager.h"
#include "core/CWrapper.h"
#include "handler/CObjectHandler.h"
#include "object/CBuilding.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include "object/CQuest.h"
#include "veventloop.h"

#include <any>
#include <array>
#include <charconv>
#include <cstdlib>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <typeinfo>

namespace {
constexpr auto StateKey = "plugin_citySevenSunsWarningState";
constexpr auto GlobalsKey = "plugin_citySourceGlobals";
constexpr auto ActorKey = "plugin_citySevenSunsWarningActor";
constexpr auto DefinitionKey = "sevenSunsWarningDefinition";
constexpr auto ActorName = "cityAr0601Actor2";
constexpr auto QuestId = "citySevenSunsWarningLead";
constexpr auto DialogueFingerprint = "263ba285fac3cc7d486ce0c4223ce4af574b257b7ce224d8755b988906df6aac";

void require(bool condition, const char *message) {
    if (!condition)
        throw std::runtime_error(message);
}

int integer(const json &value) {
    require(value.is_number_integer(), "Seven Suns requires an integer source value");
    const auto encoded = value.dump();
    int result = 0;
    const auto parsed = std::from_chars(encoded.data(), encoded.data() + encoded.size(), result);
    require(parsed.ec == std::errc{} && parsed.ptr == encoded.data() + encoded.size(),
            "Seven Suns integer is outside the signed native source range");
    return result;
}

std::shared_ptr<vstd::meta> metadata(const std::shared_ptr<CGameObject> &owner) {
    require(owner != nullptr, "Missing Seven Suns field owner");
    const auto &type = typeid(*owner);
    if (type == typeid(CMap))
        return CMap::static_meta();
    if (type == typeid(CBuilding))
        return CBuilding::static_meta();
    if (type == typeid(CWrapper<CBuilding>))
        return CWrapper<CBuilding>::static_meta();
    if (type == typeid(CCreature))
        return CCreature::static_meta();
    throw std::runtime_error("Unsupported Seven Suns field provider");
}

template <typename T> std::optional<T> stored(const std::shared_ptr<CGameObject> &owner, const std::string &key) {
    const auto property = metadata(owner)->find_property(key, owner);
    if (!property)
        return std::nullopt;
    using Slot = vstd::detail::dynamic_property_impl<CGameObject, T>;
    require(typeid(*property) == typeid(Slot), "Seven Suns requires ordinary typed storage");
    return std::any_cast<T>(static_cast<const Slot &>(*property).get(std::any{}));
}

template <typename T> struct Field {
    std::shared_ptr<CGameObject> owner;
    std::string key;
    std::shared_ptr<vstd::property> identity;
    std::optional<T> value;
    Field(std::shared_ptr<CGameObject> owner, std::string key) : owner(std::move(owner)), key(std::move(key)) {
        identity = metadata(this->owner)->find_property(this->key, this->owner);
        value = stored<T>(this->owner, this->key);
    }
    void check() const {
        require(metadata(owner)->find_property(key, owner) == identity && stored<T>(owner, key) == value,
                "Seven Suns field identity or value changed");
    }
    void write(T next, const std::function<void()> &checkCurrent) {
        checkCurrent();
        check();
        if (!identity) {
            metadata(owner)->set_dynamic_property<CGameObject, T>(key, owner, next);
            identity = metadata(owner)->find_property(key, owner);
        } else {
            using Slot = vstd::detail::dynamic_property_impl<CGameObject, T>;
            static_cast<Slot &>(*identity).set(std::any{}, next);
        }
        value = std::move(next);
        check();
        checkCurrent();
        owner->notifyPropertyChanged(key);
        check();
        checkCurrent();
    }
};

json document(const std::optional<std::string> &encoded, json initial, std::size_t limit) {
    if (!encoded || encoded->empty())
        return initial;
    require(encoded->size() <= limit, "Oversized Seven Suns source storage");
    constexpr std::string_view prefix = "city-json:";
    const std::string_view text(*encoded);
    return json::parse(text.starts_with(prefix) ? text.substr(prefix.size()) : text);
}

std::string encode(const json &value) { return "city-json:" + value.dump(); }

bool keys(const json &value, std::initializer_list<const char *> names) {
    if (!value.is_object() || value.size() != names.size())
        return false;
    for (const auto *name : names)
        if (!value.contains(name))
            return false;
    return true;
}

json initialState() {
    return json{{"version", 1},     {"status", "active"},
                {"revision", 0},    {"globals", {{"AskedForTour", 0}, {"CheckedSevenSuns", 0}}},
                {"lastEdge", -1},   {"cursor", 0},
                {"journal", false}, {"edges", json::array()}};
}

void validateState(const json &row) {
    require(keys(row, {"version", "status", "revision", "globals", "lastEdge", "cursor", "journal", "edges"}) &&
                row.at("version").is_number_integer() && integer(row.at("version")) == 1 &&
                row.at("status").is_string() && row.at("revision").is_number_integer() &&
                integer(row.at("revision")) >= 0 && integer(row.at("revision")) < 1000000 &&
                row.at("lastEdge").is_number_integer() && row.at("cursor").is_number_integer() &&
                row.at("journal").is_boolean() && row.at("edges").is_array() && row.at("edges").size() <= 3 &&
                keys(row.at("globals"), {"AskedForTour", "CheckedSevenSuns"}),
            "Malformed Seven Suns warning receipt");
    const auto &globals = row.at("globals");
    require(globals.at("AskedForTour").is_number_integer() && globals.at("CheckedSevenSuns").is_number_integer(),
            "Malformed Seven Suns globals");
    const auto checked = integer(globals.at("CheckedSevenSuns"));
    const auto status = row.at("status").get<std::string>();
    const auto cursor = integer(row.at("cursor"));
    require((status == "active" || status == "retired") &&
                (cursor == 0 || cursor == 1 || cursor == 2 || cursor == 3 || cursor == 7 || cursor == 8) &&
                integer(row.at("lastEdge")) >= -1 && integer(row.at("lastEdge")) <= 16 &&
                (status == "retired") == row.at("journal").get<bool>(),
            "Unsettled or unsupported Seven Suns warning receipt");
    const auto last = integer(row.at("lastEdge"));
    if (last == -1) {
        require(integer(row.at("revision")) == 0 && cursor == 0 && status == "active" && row.at("edges").empty(),
                "Malformed initial Seven Suns warning receipt");
    } else {
        const bool terminal = last == 9 || last == 15 || last == 16;
        const int target = last == 0                             ? 2
                           : last == 1 || last == 2              ? 1
                           : last == 3 || last == 15             ? 7
                           : last == 4 || last == 7 || last == 9 ? 3
                                                                 : 8;
        require((last >= 0 && last <= 9 || last == 15 || last == 16) && integer(row.at("revision")) > 0 &&
                    checked == 2 && cursor == target && (status == "retired") == terminal,
                "Seven Suns receipt cursor does not match its committed source edge");
        require(!row.at("edges").empty() && integer(row.at("edges").at(row.at("edges").size() - 1)) == last,
                "Seven Suns receipt lost its ordered source edge prefix");
        for (const auto &edge : row.at("edges"))
            static_cast<void>(integer(edge));
    }
}

struct Edge {
    int index;
    int from;
    int to;
    bool asked;
    bool setAsked;
    bool setChecked;
    bool escape;
};
constexpr std::array<Edge, 12> Edges{{
    {0, 0, 2, false, false, true, false},
    {1, 0, 1, false, true, true, false},
    {2, 0, 1, false, false, true, false},
    {3, 1, 7, false, false, false, false},
    {4, 1, 3, false, false, false, false},
    {5, 1, 8, true, false, false, false},
    {6, 1, 8, false, false, false, false},
    {7, 2, 3, false, false, false, false},
    {8, 2, 8, false, false, false, false},
    {9, 3, 3, false, false, false, true},
    {15, 7, 7, false, false, false, true},
    {16, 8, 8, false, false, false, true},
}};

struct ActorSnapshot {
    std::shared_ptr<CCreature> actor;
    Coords coords;
    int hp, mana, gold, exp;
    bool npc;
    decltype(actor->getItems()) items;
    decltype(actor->getEquipped()) equipped;
    decltype(actor->getEffects()) effects;
    explicit ActorSnapshot(std::shared_ptr<CCreature> actor)
        : actor(std::move(actor)), coords(this->actor->getCoords()), hp(this->actor->getHp()),
          mana(this->actor->getMana()), gold(this->actor->getGold()), exp(this->actor->getExp()),
          npc(this->actor->isNpc()), items(this->actor->getItems()), equipped(this->actor->getEquipped()),
          effects(this->actor->getEffects()) {}
    void check() const {
        require(actor->isAlive() && actor->isNpc() == npc && actor->getCoords() == coords && actor->getHp() == hp &&
                    actor->getMana() == mana && actor->getGold() == gold && actor->getExp() == exp &&
                    actor->getItems() == items && actor->getEquipped() == equipped && actor->getEffects() == effects,
                "Seven Suns departure changed living actor state or possessions");
    }
};

pybind11::object questOverride(const std::shared_ptr<CQuest> &quest, const char *method) {
    auto result = CPythonOverrides::find_override(quest.get(), method);
    if (result.is_none()) {
        auto wrapped = pybind11::get_override(quest.get(), method);
        if (wrapped)
            result = std::move(wrapped);
    }
    return result;
}

void captureJournalStrict(const std::shared_ptr<CQuest> &quest) {
    pybind11::gil_scoped_acquire gil;
    auto callback = questOverride(quest, "captureJournal");
    if (!callback.is_none())
        callback(false);
}

std::string journalTextStrict(const std::shared_ptr<CQuest> &quest, const char *method) {
    pybind11::gil_scoped_acquire gil;
    auto callback = questOverride(quest, method);
    if (!callback.is_none())
        return callback().cast<std::string>();
    const std::string_view name(method);
    if (name == "getObjective")
        return quest->CQuest::getObjective();
    if (name == "getReward")
        return quest->CQuest::getReward();
    return quest->CQuest::getHint();
}
} // namespace

struct CSevenSunsDialogue::State {
    enum class ActorPhase { Registered, Removing, Retired };
    std::weak_ptr<CGame> game;
    std::shared_ptr<CGameContext> context;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CPlayer> player;
    std::shared_ptr<CGameObject> clock;
    std::shared_ptr<CCreature> actor;
    std::shared_ptr<CQuest> journal;
    CGameContext::TransitionGeneration generation;
    std::uint64_t epoch;
    std::function<void()> requireCaller;
    Field<std::string> definition;
    Field<std::string> receipt;
    Field<std::shared_ptr<CGameObject>> retained;
    Field<std::string> globals;
    json sourceGlobals;
    json row;
    json edges = json::array();
    int cursor = 0;
    bool firstChoice = true;
    bool closed = false;
    bool poisoned = false;
    bool mutating = false;
    ActorPhase actorPhase = ActorPhase::Registered;
    static std::mutex sessionsMutex;
    static std::map<const CMap *, State *> sessions;

    State(std::shared_ptr<CGame> game, std::shared_ptr<CMap> map, std::shared_ptr<CGameObject> clock,
          std::shared_ptr<CCreature> actor, std::function<void()> caller)
        : game(game), context(game->getContext()), map(std::move(map)), player(this->map->getAssignedPlayer()),
          clock(std::move(clock)), actor(std::move(actor)), generation(context->captureTransitionGeneration()),
          epoch(game->getMapBindingEpoch()), requireCaller(std::move(caller)), definition(this->clock, DefinitionKey),
          receipt(this->map, StateKey), retained(this->clock, ActorKey), globals(this->map, GlobalsKey),
          sourceGlobals(document(globals.value, json::object(), 65536)),
          row(document(receipt.value, initialState(), 4096)) {
        require(sourceGlobals.is_object() && sourceGlobals.size() <= 256, "Malformed city source-global scopes");
        if (sourceGlobals.contains("GLOBAL"))
            require(sourceGlobals.at("GLOBAL").is_object() && sourceGlobals.at("GLOBAL").size() <= 1024,
                    "Malformed city GLOBAL namespace");
        const auto snapshot = globalSnapshot();
        if (!receipt.value || receipt.value->empty())
            row["globals"] = snapshot;
    }

    static std::string canonicalName(std::string name) {
        for (auto &letter : name)
            if (letter >= 'a' && letter <= 'z')
                letter = static_cast<char>(letter - 'a' + 'A');
        return name;
    }

    std::optional<std::string> globalKey(const char *name) const {
        if (!sourceGlobals.contains("GLOBAL"))
            return std::nullopt;
        std::optional<std::string> result;
        const auto wanted = canonicalName(name);
        for (const auto &[key, ignored] : sourceGlobals.at("GLOBAL").items())
            if (canonicalName(key) == wanted) {
                require(!result, "Ambiguous case aliases in city GLOBAL namespace");
                result = key;
            }
        return result;
    }

    int global(const char *name) const {
        const auto key = globalKey(name);
        if (!key)
            return 0;
        const auto &value = sourceGlobals.at("GLOBAL").at(*key);
        require(value.is_number_integer(), "Unsupported city source-global value type");
        return integer(value);
    }

    json globalSnapshot() const {
        return json{{"AskedForTour", global("AskedForTour")}, {"CheckedSevenSuns", global("CheckedSevenSuns")}};
    }

    void writeGlobal(const char *name, int value, const std::function<void()> &checkCurrent) {
        if (!sourceGlobals.contains("GLOBAL"))
            sourceGlobals["GLOBAL"] = json::object();
        const auto key = globalKey(name).value_or(name);
        sourceGlobals["GLOBAL"][key] = value;
        require(sourceGlobals.size() <= 256 && sourceGlobals.at("GLOBAL").size() <= 1024,
                "City source-global insertion exceeded its count bound");
        auto encoded = encode(sourceGlobals);
        require(encoded.size() <= 65536, "City source-global storage exceeded its bound");
        globals.write(std::move(encoded), checkCurrent);
        row["globals"] = globalSnapshot();
        writeRow(checkCurrent);
    }

    ~State() {
        std::lock_guard lock(sessionsMutex);
        auto found = sessions.find(map.get());
        if (found != sessions.end() && found->second == this)
            sessions.erase(found);
    }

    void claim() {
        std::lock_guard lock(sessionsMutex);
        if (auto found = sessions.find(map.get()); found != sessions.end()) {
            if (found->second->mutating)
                found->second->poisoned = true;
            throw std::runtime_error("A Seven Suns warning dialogue already owns this map");
        }
        sessions.emplace(map.get(), this);
    }

    void check(bool caller = true) const {
        require(vstd::event_loop<>::instance()->isMainThread(), "Seven Suns requires the engine owner thread");
        if (caller && requireCaller)
            requireCaller();
        auto owner = game.lock();
        require(owner && !closed && !poisoned && context->isActive() && owner->getContext() == context &&
                    context->isTransitionGenerationCurrent(generation) && owner->getMap() == map &&
                    owner->getMapBindingEpoch() == epoch && map->getGame() == owner &&
                    map->getAssignedPlayer() == player && player && player->isAlive() &&
                    map->getObjectByName("player") == player && player->getGame() == owner &&
                    map->getObjectByName("cityClock") == clock && clock->getGame() == owner &&
                    clock->getName() == "cityClock" && actor && actor->getGame() == owner &&
                    actor->getName() == ActorName && actor->isAlive() && actor->isNpc(),
                "Seven Suns dialogue binding changed");
        require(stored<std::string>(actor, "sourceActor") == std::optional<std::string>{"AR0601#actor2"} &&
                    stored<std::string>(actor, "sourceArea") == std::optional<std::string>{"AR0601"} &&
                    stored<std::string>(actor, "simulationRegion") == std::optional<std::string>{"AR0601"} &&
                    stored<std::string>(actor, "sourceCreature") == std::optional<std::string>{"DOPPSM"} &&
                    stored<std::string>(actor, "sourceDialogue") == std::optional<std::string>{"DOPPSM"},
                "Seven Suns warning actor source identity changed");
        const auto registered = map->getObjectByName(ActorName);
        require(actorPhase == ActorPhase::Registered
                    ? registered == actor
                    : !registered || (actorPhase == ActorPhase::Removing && registered == actor),
                "Seven Suns warning actor registration changed");
        if (actorPhase == ActorPhase::Registered)
            require(!CSevenSunsDialogue::hasSceneLifetimeOwner(owner, map, actor, false),
                    "A registered Seven Suns actor has an unsettled scene lifetime owner");
        else if (!registered)
            require(CSevenSunsDialogue::hasSceneLifetimeOwner(owner, map, actor, true),
                    "Seven Suns detached actor lost its scene lifetime owner");
        if (actorPhase == ActorPhase::Retired)
            require(retained.value == std::optional<std::shared_ptr<CGameObject>>{actor},
                    "Seven Suns retired actor lost its exact retained owner");
        const auto a = actor->getCoords();
        const auto p = player->getCoords();
        const auto dx = static_cast<std::int64_t>(a.x) - p.x;
        const auto dy = static_cast<std::int64_t>(a.y) - p.y;
        require(a.z == p.z && std::abs(dx) + std::abs(dy) <= 1 &&
                    !stored<bool>(map, "plugin_cityFlag_cityCompleted").value_or(false) &&
                    !stored<bool>(map, "plugin_cityFlag_poisonFatal").value_or(false) &&
                    stored<std::string>(map, "plugin_cityCustodyState").value_or("") != "hearing" &&
                    !stored<bool>(actor, "plugin_cityPetrified").value_or(false),
                "Seven Suns warning interaction is no longer available");
        const int phase = stored<int>(map, "plugin_cityPhase").value_or(5);
        require(phase >= stored<int>(actor, "phaseMin").value_or(5) &&
                    phase <= stored<int>(actor, "phaseMax").value_or(7),
                "Seven Suns warning phase changed");
        definition.check();
        receipt.check();
        retained.check();
        globals.check();
        if (journal) {
            std::size_t matching = 0;
            for (const auto &entry : player->getQuests())
                if (entry && entry->getTypeId() == QuestId) {
                    require(entry == journal && entry->getGame() == owner, "Seven Suns journal owner changed");
                    ++matching;
                }
            require(matching == 1, "Seven Suns journal is no longer active");
            for (const auto &entry : player->getCompletedQuests())
                require(!entry || entry->getTypeId() != QuestId, "Seven Suns journal was completed unexpectedly");
        }
    }

    void writeRow(const std::function<void()> &checkCurrent) {
        auto encoded = encode(row);
        require(encoded.size() <= 4096, "Seven Suns receipt exceeded its bound");
        receipt.write(std::move(encoded), checkCurrent);
    }

    void recordFirstChoice(const std::function<void()> &checkCurrent) {
        Field<std::string> talked(map, "plugin_cityTalked");
        auto talks = document(talked.value, json::object(), 65536);
        require(talks.is_object() && talks.size() <= 2048, "Malformed city conversation records");
        talks[ActorName] = json{{"label", "Merchant"}, {"creature", "DOPPSM"}, {"area", "AR0601"}};
        require(talks.size() <= 2048 && encode(talks).size() <= 65536,
                "City conversation insertion exceeded its bound");
        talked.write(encode(talks), checkCurrent);
        Field<int> count(actor, "plugin_cityTalkCount");
        require(count.value.value_or(0) >= 0 && count.value.value_or(0) < 1000000, "Invalid city talk count");
        count.write(count.value.value_or(0) + 1, checkCurrent);
        Field<bool> frozen(map, "plugin_cityHistoryFrozen");
        if (!frozen.value.value_or(false)) {
            Field<std::string> history(map, "plugin_cityHistory");
            auto choices = document(history.value, json::object(), 65536);
            require(choices.is_object(), "Malformed city history");
            for (const auto *key : {"aldeth", "tenya", "eldoth"})
                if (!choices.contains(key))
                    choices[key] = "unspecified";
            Field<std::string> profile(map, "plugin_cityStartingProfile");
            auto starting = document(profile.value, json::object(), 65536);
            require(starting.is_object(), "Malformed city starting profile");
            starting["history"] = choices;
            starting["historyFrozen"] = true;
            require(encode(choices).size() <= 65536 && encode(starting).size() <= 65536,
                    "City history freeze exceeded its storage bound");
            history.write(encode(choices), checkCurrent);
            profile.write(encode(starting), checkCurrent);
            frozen.write(true, checkCurrent);
        }
    }

    void preflight(const Edge &edge) const {
        auto next = sourceGlobals;
        if (edge.setAsked || edge.setChecked) {
            if (!next.contains("GLOBAL"))
                next["GLOBAL"] = json::object();
            if (edge.setAsked)
                next["GLOBAL"][globalKey("AskedForTour").value_or("AskedForTour")] = 1;
            if (edge.setChecked)
                next["GLOBAL"][globalKey("CheckedSevenSuns").value_or("CheckedSevenSuns")] = 2;
            require(next.size() <= 256 && next.at("GLOBAL").size() <= 1024 && encode(next).size() <= 65536,
                    "Seven Suns source-global insertion does not fit its bounded store");
        }
        if (!firstChoice)
            return;
        Field<std::string> talked(map, "plugin_cityTalked");
        auto talks = document(talked.value, json::object(), 65536);
        require(talks.is_object(), "Malformed city conversation records");
        talks[ActorName] = json{{"label", "Merchant"}, {"creature", "DOPPSM"}, {"area", "AR0601"}};
        require(talks.size() <= 2048 && encode(talks).size() <= 65536,
                "Seven Suns conversation insertion does not fit its bounded store");
        Field<int> count(actor, "plugin_cityTalkCount");
        require(count.value.value_or(0) >= 0 && count.value.value_or(0) < 1000000, "Invalid city talk count");
        if (!stored<bool>(map, "plugin_cityHistoryFrozen").value_or(false)) {
            auto history = document(stored<std::string>(map, "plugin_cityHistory"), json::object(), 65536);
            auto profile = document(stored<std::string>(map, "plugin_cityStartingProfile"), json::object(), 65536);
            require(history.is_object() && profile.is_object(), "Malformed city history/profile");
            for (const auto *key : {"aldeth", "tenya", "eldoth"})
                if (!history.contains(key))
                    history[key] = "unspecified";
            profile["history"] = history;
            profile["historyFrozen"] = true;
            require(encode(history).size() <= 65536 && encode(profile).size() <= 65536,
                    "Seven Suns history freeze does not fit its bounded store");
        }
    }
};

std::mutex CSevenSunsDialogue::State::sessionsMutex;
std::map<const CMap *, CSevenSunsDialogue::State *> CSevenSunsDialogue::State::sessions;

CSevenSunsDialogue::CSevenSunsDialogue(std::unique_ptr<State> state) : state(std::move(state)) {}
CSevenSunsDialogue::~CSevenSunsDialogue() = default;
int CSevenSunsDialogue::readInteger(const json &value) { return integer(value); }
bool CSevenSunsDialogue::hasSceneLifetimeOwner(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                               const std::shared_ptr<CCreature> &actor, bool requireDetached) {
    auto scene = game->getSceneManager();
    return requireDetached ? scene->isSceneObjectRetired(map, actor) : scene->containsSceneRetiredObject(map, actor);
}

std::unique_ptr<CSevenSunsDialogue> CSevenSunsDialogue::begin(std::weak_ptr<CGame> weakGame,
                                                              std::shared_ptr<CGameObject> clock,
                                                              std::shared_ptr<CCreature> actor,
                                                              std::function<void()> requireCaller) {
    require(vstd::event_loop<>::instance()->isMainThread(), "Seven Suns requires the engine owner thread");
    if (requireCaller)
        requireCaller();
    auto game = weakGame.lock();
    require(game != nullptr, "Seven Suns game expired");
    auto map = game->getMap();
    require(map && typeid(*map) == typeid(CMap) && map->getMapName() == "baldursGate" && clock &&
                map->getObjectByName("cityClock") == clock && clock->getGame() == game,
            "Seven Suns requires its authored current map and clock");
    {
        std::lock_guard lock(State::sessionsMutex);
        if (auto found = State::sessions.find(map.get()); found != State::sessions.end()) {
            if (found->second->mutating)
                found->second->poisoned = true;
            throw std::runtime_error("A Seven Suns warning dialogue already owns this map");
        }
    }
    auto lease = map->tryBeginUnsafeOperation();
    require(lease.has_value(), "Seven Suns save admission refused");
    auto value = std::make_unique<State>(game, map, clock, actor, std::move(requireCaller));
    validateState(value->row);
    const bool retired = value->row.at("status").get<std::string>() == "retired";
    require(game->getSceneManager()->containsSceneRetiredObject(map, actor) == retired,
            "Seven Suns scene lifetime owner disagrees with its source receipt");
    if (retired) {
        auto owner = value->retained.value ? std::dynamic_pointer_cast<CCreature>(*value->retained.value) : nullptr;
        require(owner && owner == actor && !map->getObjectByName(ActorName), "Orphan retired Seven Suns actor");
        value->actorPhase = State::ActorPhase::Retired;
        value->cursor = integer(value->row.at("cursor"));
        std::size_t journalCount = 0;
        if (value->player) {
            for (const auto &quest : value->player->getQuests())
                if (quest && quest->getTypeId() == QuestId && quest->getGame() == game) {
                    value->journal = quest;
                    ++journalCount;
                }
            for (const auto &quest : value->player->getCompletedQuests())
                require(!quest || quest->getTypeId() != QuestId,
                        "Retired Seven Suns journal has a completed duplicate");
        }
        require(journalCount == 1, "Retired Seven Suns journal lost its exact active owner");
    } else {
        require(!value->retained.value, "Orphan Seven Suns warning actor reference");
        if (value->player) {
            for (const auto &quest : value->player->getQuests())
                require(!quest || quest->getTypeId() != QuestId, "Orphan Seven Suns warning journal");
            for (const auto &quest : value->player->getCompletedQuests())
                require(!quest || quest->getTypeId() != QuestId, "Orphan completed Seven Suns warning journal");
        }
    }
    const auto definition = document(value->definition.value, json(), 1024);
    if (!(keys(definition, {"version", "dialogue", "fingerprint", "journalQuest"}) &&
          definition.at("version").is_number_integer() && integer(definition.at("version")) == 1 &&
          definition.at("dialogue").is_string() && definition.at("dialogue").get<std::string>() == "DOPPSM" &&
          definition.at("fingerprint").is_string() &&
          definition.at("fingerprint").get<std::string>() == DialogueFingerprint &&
          definition.at("journalQuest").is_string() && definition.at("journalQuest").get<std::string>() == QuestId)) {
        lease->finish();
        throw std::runtime_error("Seven Suns warning content capability is unavailable");
    }
    try {
        value->check();
        value->claim();
    } catch (...) {
        lease->finish();
        throw;
    }
    lease->finish();
    return std::unique_ptr<CSevenSunsDialogue>(new CSevenSunsDialogue(std::move(value)));
}

void CSevenSunsDialogue::requireCurrent() const { state->check(); }

json CSevenSunsDialogue::view() const {
    state->check();
    json choices = json::array();
    json automatic = nullptr;
    const bool retired = state->actorPhase == State::ActorPhase::Retired;
    if (!retired)
        for (const auto &edge : Edges)
            if (edge.from == state->cursor && (!edge.asked || state->global("AskedForTour") == 1)) {
                if (edge.escape)
                    automatic = edge.index;
                else
                    choices[choices.size()] = edge.index;
            }
    return json{{"status", retired ? "retired" : "ready"},
                {"capabilityVersion", 1},
                {"state", state->cursor},
                {"revision", state->row.at("revision")},
                {"choices", choices},
                {"automaticEdge", automatic},
                {"journal", retired ? json{{"strref", 26986}, {"rawFlags", 92}} : json(nullptr)}};
}

json CSevenSunsDialogue::advance(int revision, int edgeIndex) {
    if (state->mutating) {
        state->poisoned = true;
        throw std::runtime_error("Reentrant Seven Suns transition");
    }
    state->check();
    auto game = state->game.lock();
    require(game != nullptr, "Seven Suns game expired");
    require(!state->mutating && state->actorPhase == State::ActorPhase::Registered &&
                integer(state->row.at("revision")) == revision && revision < 999999,
            "Stale or repeated Seven Suns transition");
    const Edge *selected = nullptr;
    for (const auto &edge : Edges)
        if (edge.index == edgeIndex && edge.from == state->cursor &&
            (!edge.asked || state->global("AskedForTour") == 1))
            selected = &edge;
    require(selected != nullptr, "Unsupported Seven Suns dialogue transition");
    state->preflight(*selected);
    auto lease = state->map->tryBeginUnsafeOperation();
    require(lease.has_value(), "Seven Suns save admission refused");
    state->mutating = true;
    auto check = [&] {
        state->check();
        require(lease->isSaveAdmissionHealthy(), "Seven Suns mutation admission changed or was quarantined");
    };
    try {
        auto barrier = game->getObjectHandler()->beginDefeatConstruction(check);
        check();
        ActorSnapshot original(state->actor);
        ActorSnapshot originalPlayer(state->player);
        if (selected->escape) {
            for (const auto &quest : state->player->getQuests())
                require(!quest || quest->getTypeId() != QuestId, "Orphan Seven Suns warning journal before escape");
            for (const auto &quest : state->player->getCompletedQuests())
                require(!quest || quest->getTypeId() != QuestId, "Orphan completed Seven Suns journal before escape");
            state->retained.write(state->actor, check);
        }
        state->row["status"] = "pending";
        state->row["lastEdge"] = edgeIndex;
        state->edges[state->edges.size()] = edgeIndex;
        require(state->edges.size() <= 3, "Seven Suns conversation exceeded its finite edge prefix");
        state->row["edges"] = state->edges;
        state->row["globals"] = state->globalSnapshot();
        state->writeRow(check);
        if (selected->setAsked)
            state->writeGlobal("AskedForTour", 1, check);
        if (selected->setChecked)
            state->writeGlobal("CheckedSevenSuns", 2, check);
        if (state->firstChoice)
            state->recordFirstChoice(check);
        if (selected->escape) {
            state->actorPhase = State::ActorPhase::Removing;
            game->getSceneManager()->retireObjectWithoutEvents(game, state->map, state->actor, check);
            state->actorPhase = State::ActorPhase::Retired;
            check();
            original.check();
            state->player->addQuest(QuestId);
            check();
            std::shared_ptr<CQuest> journal;
            for (const auto &quest : state->player->getQuests())
                if (quest && quest->getTypeId() == QuestId) {
                    require(!journal, "Duplicate Seven Suns warning journal");
                    journal = quest;
                }
            require(journal != nullptr, "Seven Suns warning journal was not added");
            state->journal = journal;
            require(journal->getGame() == game &&
                        (typeid(*journal) == typeid(CQuest) || typeid(*journal) == typeid(CWrapper<CQuest>)),
                    "Seven Suns warning journal has an unsupported native provider");
            auto requireJournal = [&] {
                check();
                std::size_t matching = 0;
                for (const auto &quest : state->player->getQuests())
                    if (quest && quest->getTypeId() == QuestId) {
                        require(quest == journal && quest->getGame() == game, "Seven Suns journal owner was replaced");
                        ++matching;
                    }
                require(matching == 1, "Seven Suns journal is no longer active");
                for (const auto &quest : state->player->getCompletedQuests())
                    require(!quest || quest->getTypeId() != QuestId,
                            "Seven Suns warning journal has a completed duplicate");
            };
            requireJournal();
            captureJournalStrict(journal);
            requireJournal();
            require(!journalTextStrict(journal, "getObjective").empty(), "Seven Suns warning journal is unreadable");
            requireJournal();
            require(!journalTextStrict(journal, "getReward").empty(),
                    "Seven Suns warning journal reward description is unreadable");
            requireJournal();
            require(!journalTextStrict(journal, "getHint").empty(), "Seven Suns warning journal hint is unreadable");
            requireJournal();
            original.check();
            state->row["journal"] = true;
        }
        state->cursor = selected->to;
        state->row["cursor"] = state->cursor;
        state->row["revision"] = revision + 1;
        state->row["status"] = selected->escape ? "retired" : "active";
        state->writeRow(check);
        original.check();
        originalPlayer.check();
        check();
        state->firstChoice = false;
        state->mutating = false;
        lease->finish();
        return view();
    } catch (...) {
        state->poisoned = true;
        state->mutating = false;
        lease->quarantine();
        throw;
    }
}

json CSevenSunsDialogue::close() {
    require(vstd::event_loop<>::instance()->isMainThread(), "Seven Suns requires the engine owner thread");
    require(!state->mutating, "Cannot close an admitted Seven Suns mutation");
    const int revision = integer(state->row.at("revision"));
    state->closed = true;
    return json{{"status", "closed"},   {"capabilityVersion", 1},   {"state", state->cursor},
                {"revision", revision}, {"choices", json::array()}, {"automaticEdge", nullptr},
                {"journal", nullptr}};
}
