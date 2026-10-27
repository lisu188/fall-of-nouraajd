// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
#include "handler/CSevenSunsMerchantDialogue.h"
#include "core/CGame.h"
#include "core/CGameContext.h"
#include "core/CMap.h"
#include "core/CPlaytestTrace.h"
#include "core/CSceneManager.h"
#include "core/CWrapper.h"
#include "handler/CEventHandler.h"
#include "handler/CFightHandler.h"
#include "handler/CObjectHandler.h"
#include "handler/CSevenSunsMerchantStock.h"
#include "object/CBuilding.h"
#include "object/CCreature.h"
#include "object/CPlayer.h"
#include "object/CTrigger.h"
#include "veventloop.h"

#include <any>
#include <array>
#include <charconv>
#include <cstdlib>
#include <map>
#include <limits>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <typeinfo>

namespace {
constexpr auto ReceiptKey = "plugin_citySevenSunsMerchantState";
constexpr auto GlobalsKey = "plugin_citySourceGlobals";
constexpr auto CountKey = "plugin_cityDopmerTalkCount";
constexpr auto DefinitionKey = "sevenSunsMerchantDefinition";
constexpr auto Fingerprint = "e0410b2b978573d0e921a63bf3a55fd53d49c291f556b6e0a045db63762030a7";
struct Lineage {
    const char *name;
    const char *sourceActor;
    const char *area;
};
constexpr std::array<Lineage, 4> Lineages{{
    {"cityAr0601Actor1", "AR0601#actor1", "AR0601"},
    {"cityAr0601Actor3", "AR0601#actor3", "AR0601"},
    {"cityAr0602Actor1", "AR0602#actor1", "AR0602"},
    {"cityAr0602Actor2", "AR0602#actor2", "AR0602"},
}};
struct Edge {
    int index;
    int from;
    int to;
    bool checked;
    bool reveal;
    bool terminal;
};
constexpr std::array<Edge, 24> Edges{{
    {0, 0, 1, true, false, false},     {1, 0, 2, true, false, false},     {2, 0, 3, true, false, false},
    {3, 1, 1, false, false, true},     {4, 2, 4, false, false, false},    {5, 2, 5, false, false, false},
    {6, 2, 3, false, false, false},    {7, 3, 3, false, false, true},     {8, 4, 4, false, false, true},
    {9, 5, 3, false, false, false},    {10, 5, 4, false, false, false},   {11, 5, 6, false, false, false},
    {12, 6, 6, false, true, true},     {13, 7, 8, false, false, false},   {14, 7, 9, false, false, false},
    {15, 7, 9, false, false, false},   {16, 8, 8, false, false, true},    {17, 9, 9, false, true, true},
    {18, 10, 11, false, false, false}, {19, 10, 12, false, false, false}, {20, 10, 13, false, false, false},
    {21, 11, 11, false, true, true},   {22, 12, 12, false, true, true},   {23, 13, 13, false, true, true},
}};
void require(bool value, const char *message) {
    if (!value)
        throw std::runtime_error(message);
}
int integer(const json &value) {
    require(value.is_number_integer(), "DOPMER requires a signed source integer");
    const auto numeric = value.get<double>();
    require(numeric >= std::numeric_limits<int>::min() && numeric <= std::numeric_limits<int>::max(),
            "DOPMER integer exceeds signed32 authority before JSON dump");
    auto text = value.dump();
    int result = 0;
    auto parsed = std::from_chars(text.data(), text.data() + text.size(), result);
    require(parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size(), "DOPMER integer overflow");
    return result;
}
std::shared_ptr<vstd::meta> metadata(const std::shared_ptr<CGameObject> &owner) {
    require(owner != nullptr, "Missing DOPMER field owner");
    if (typeid(*owner) == typeid(CMap))
        return CMap::static_meta();
    if (typeid(*owner) == typeid(CBuilding))
        return CBuilding::static_meta();
    if (typeid(*owner) == typeid(CWrapper<CBuilding>))
        return CWrapper<CBuilding>::static_meta();
    if (typeid(*owner) == typeid(CCreature))
        return CCreature::static_meta();
    throw std::runtime_error("Unsupported DOPMER field provider");
}
template <class T> std::optional<T> stored(const std::shared_ptr<CGameObject> &owner, const std::string &key) {
    auto slot = metadata(owner)->find_property(key, owner);
    if (!slot)
        return std::nullopt;
    using Slot = vstd::detail::dynamic_property_impl<CGameObject, T>;
    require(typeid(*slot) == typeid(Slot), "DOPMER requires ordinary typed source storage");
    return std::any_cast<T>(static_cast<const Slot &>(*slot).get(std::any{}));
}
template <class T> struct Field {
    std::shared_ptr<CGameObject> owner;
    std::string key;
    std::shared_ptr<vstd::property> identity;
    std::optional<T> value;
    Field(std::shared_ptr<CGameObject> object, std::string name)
        : owner(std::move(object)), key(std::move(name)), identity(metadata(owner)->find_property(key, owner)),
          value(stored<T>(owner, key)) {}
    void check() const {
        require(metadata(owner)->find_property(key, owner) == identity && stored<T>(owner, key) == value,
                "DOPMER field identity or value changed");
    }
    void write(T next, const std::function<void()> &guard) {
        guard();
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
        guard();
        owner->notifyPropertyChanged(key);
        check();
        guard();
    }
};
json document(const std::optional<std::string> &text, json empty, std::size_t limit = 65536) {
    if (!text || text->empty())
        return empty;
    require(text->size() <= limit, "Oversized DOPMER storage");
    std::string_view value(*text), prefix = "city-json:";
    return json::parse(value.starts_with(prefix) ? value.substr(prefix.size()) : value);
}
std::string encode(const json &value) { return "city-json:" + value.dump(); }
bool keys(const json &value, std::initializer_list<const char *> names) {
    if (!value.is_object() || value.size() != names.size())
        return false;
    for (auto name : names)
        if (!value.contains(name))
            return false;
    return true;
}
std::string canonical(std::string value) {
    for (auto &c : value)
        if (c >= 'a' && c <= 'z')
            c = static_cast<char>(c - 'a' + 'A');
    return value;
}
const Lineage *lineage(const std::string &name) {
    for (const auto &row : Lineages)
        if (name == row.name)
            return &row;
    return nullptr;
}
bool definitionAvailable(const std::shared_ptr<CGameObject> &clock) {
    try {
        auto d = document(stored<std::string>(clock, DefinitionKey), json(), 1024);
        return keys(d, {"version", "dialogue", "fingerprint", "stockContract"}) && integer(d.at("version")) == 1 &&
               d.at("dialogue").get<std::string>() == "DOPMER" &&
               d.at("fingerprint").get<std::string>() == Fingerprint &&
               d.at("stockContract").get<std::string>() == "doppss-native-v1";
    } catch (...) {
        return false;
    }
}
struct ActorSnapshot {
    std::shared_ptr<CCreature> actor;
    Coords coords;
    int hp, mana, gold, exp;
    bool npc;
    decltype(actor->getItems()) items;
    decltype(actor->getEquipped()) equipment;
    decltype(actor->getEffects()) effects;
    explicit ActorSnapshot(std::shared_ptr<CCreature> value)
        : actor(std::move(value)), coords(actor->getCoords()), hp(actor->getHp()), mana(actor->getMana()),
          gold(actor->getGold()), exp(actor->getExp()), npc(actor->isNpc()), items(actor->getItems()),
          equipment(actor->getEquipped()), effects(actor->getEffects()) {}
    void check() const {
        require(actor->isAlive() && actor->getCoords() == coords && actor->getHp() == hp && actor->getMana() == mana &&
                    actor->getGold() == gold && actor->getExp() == exp && actor->isNpc() == npc &&
                    actor->getItems() == items && actor->getEquipped() == equipment && actor->getEffects() == effects,
                "DOPMER changed its old living owner or player possessions");
    }
};
} // namespace

struct CSevenSunsMerchantDialogue::State {
    enum class Phase { Registered, Preparing, Replacing, Replaced };
    std::weak_ptr<CGame> game;
    std::shared_ptr<CGameContext> context;
    std::shared_ptr<CMap> map;
    std::shared_ptr<CPlayer> player;
    std::shared_ptr<CGameObject> clock;
    std::shared_ptr<CCreature> actor, replacement;
    const Lineage *identity;
    CGameContext::TransitionGeneration generation;
    std::uint64_t epoch, region;
    int turn;
    std::function<void()> requireCaller;
    Field<std::string> definition, receipt, globals;
    Field<int> count, allegiance;
    Field<std::shared_ptr<CGameObject>> oldRef, newRef;
    json source, rows, row;
    bool interactive, mutating = false, poisoned = false, terminal = false, firstChoice = true;
    Phase phase = Phase::Registered;
    static std::mutex mutex;
    static std::map<const CMap *, State *> sessions;

    State(std::shared_ptr<CGame> owner, std::shared_ptr<CGameObject> clock, std::shared_ptr<CCreature> actor,
          const Lineage *identity, bool interactive, std::function<void()> caller)
        : game(owner), context(owner->getContext()), map(owner->getMap()), player(map->getAssignedPlayer()),
          clock(std::move(clock)), actor(std::move(actor)), identity(identity),
          generation(context->captureTransitionGeneration()), epoch(owner->getMapBindingEpoch()),
          region(CSevenSunsMerchantDialogue::regionEpoch(owner, map)), turn(map->getTurn()),
          requireCaller(std::move(caller)), definition(this->clock, DefinitionKey), receipt(map, ReceiptKey),
          globals(map, GlobalsKey), count(this->actor, CountKey), allegiance(this->actor, "sourceAllegiance"),
          oldRef(this->clock, std::string("plugin_citySevenSunsMerchantOld_") + identity->name),
          newRef(this->clock, std::string("plugin_citySevenSunsMerchantNew_") + identity->name),
          source(document(globals.value, json::object())),
          rows(document(receipt.value, json{{"version", 1}, {"actors", json::object()}})), interactive(interactive) {
        require(source.is_object() && source.size() <= 256, "Malformed city source-global scopes");
        if (source.contains("GLOBAL"))
            require(source.at("GLOBAL").is_object() && source.at("GLOBAL").size() <= 1024,
                    "Malformed city GLOBAL namespace");
        require(keys(rows, {"version", "actors"}) && integer(rows.at("version")) == 1 &&
                    rows.at("actors").is_object() && rows.at("actors").size() <= 4,
                "Malformed DOPMER receipt collection");
        for (const auto &[name, value] : rows.at("actors").items()) {
            require(lineage(name), "Foreign DOPMER lineage receipt");
            require(value.is_object() && value.contains("status") && value.at("status").is_string(),
                    "Malformed DOPMER lineage receipt");
            const auto status = value.at("status").get<std::string>();
            require(status == "active" || status == "closed" || status == "replaced",
                    "Unsettled DOPMER lineage requires verified restore");
        }
        const int n = count.value.value_or(0);
        require(n >= 0 && n <= 1000000, "Invalid DOPMER source talk count");
        row = rows.at("actors").contains(identity->name) ? rows.at("actors").at(identity->name)
                                                         : json{{"version", 1},
                                                                {"status", "active"},
                                                                {"revision", 0},
                                                                {"sourceTalkCount", n},
                                                                {"entry", 0},
                                                                {"cursor", 0},
                                                                {"lastEdge", -1},
                                                                {"edges", json::array()},
                                                                {"globals", globalSnapshot()},
                                                                {"settledTurn", -1},
                                                                {"predicate", nullptr},
                                                                {"stock", nullptr}};
        validateRow();
        if (row.at("status").get<std::string>() == "replaced") {
            phase = Phase::Replaced;
            replacement = newRef.value ? std::dynamic_pointer_cast<CCreature>(*newRef.value) : nullptr;
        } else
            require(!oldRef.value && !newRef.value, "Orphan DOPMER retained owner");
    }
    ~State() {
        std::lock_guard lock(mutex);
        auto found = sessions.find(map.get());
        if (found != sessions.end() && found->second == this)
            sessions.erase(found);
    }
    std::optional<std::string> globalKey(const char *name) const {
        if (!source.contains("GLOBAL"))
            return std::nullopt;
        std::optional<std::string> result;
        for (const auto &[key, ignored] : source.at("GLOBAL").items())
            if (canonical(key) == canonical(name)) {
                require(!result, "Ambiguous city GLOBAL aliases");
                result = key;
            }
        return result;
    }
    int global(const char *name) const {
        auto key = globalKey(name);
        return key ? integer(source.at("GLOBAL").at(*key)) : 0;
    }
    json globalSnapshot() const {
        return json{{"CheckedSevenSuns", global("CheckedSevenSuns")},
                    {"Doppleganger", global("Doppleganger")},
                    {"Laola", global("Laola")}};
    }
    void validateRow() const {
        require(keys(row, {"version", "status", "revision", "sourceTalkCount", "entry", "cursor", "lastEdge", "edges",
                           "globals", "settledTurn", "predicate", "stock"}) &&
                    integer(row.at("version")) == 1 && row.at("status").is_string() &&
                    integer(row.at("revision")) >= 0 && integer(row.at("revision")) < 1000000 &&
                    integer(row.at("sourceTalkCount")) == count.value.value_or(0) && row.at("edges").is_array() &&
                    row.at("edges").size() <= 4,
                "Malformed or inconsistent DOPMER receipt");
        const auto status = row.at("status").get<std::string>();
        require(status == "active" || status == "closed" || status == "replaced",
                "Unsettled DOPMER receipt requires restore");
        int cursor = integer(row.at("entry"));
        require(cursor == 0 || cursor == 7 || cursor == 10, "Unsupported DOPMER source entry");
        bool ended = false;
        int last = -1;
        for (const auto &id : row.at("edges")) {
            const Edge *edge = nullptr;
            for (const auto &candidate : Edges)
                if (candidate.index == integer(id) && candidate.from == cursor)
                    edge = &candidate;
            require(edge && !ended, "DOPMER receipt lost its exact source path");
            cursor = edge->to;
            ended = edge->terminal;
            last = edge->index;
        }
        require(integer(row.at("cursor")) == cursor && integer(row.at("lastEdge")) == last &&
                    (status != "closed" || ended),
                "DOPMER receipt cursor disagrees with its path");
        require(row.at("globals").is_object(), "Malformed DOPMER source-global audit");
        for (const auto *name : {"CheckedSevenSuns", "Doppleganger", "Laola"})
            static_cast<void>(integer(row.at("globals").at(name)));
        static_cast<void>(integer(row.at("settledTurn")));
    }
    void claim() {
        std::lock_guard lock(mutex);
        if (auto found = sessions.find(map.get()); found != sessions.end()) {
            if (found->second->mutating)
                found->second->poisoned = true;
            throw std::runtime_error("A DOPMER owner already holds this city");
        }
        sessions.emplace(map.get(), this);
    }
    void check(bool validateStock = true) const {
        require(vstd::event_loop<>::instance()->isMainThread(), "DOPMER requires engine owner thread");
        if (requireCaller)
            requireCaller();
        auto owner = game.lock();
        require(owner && !poisoned && context->isActive() && owner->getContext() == context &&
                    context->isTransitionGenerationCurrent(generation) && owner->getMap() == map &&
                    owner->getMapBindingEpoch() == epoch &&
                    CSevenSunsMerchantDialogue::regionEpoch(owner, map) == region && map->getTurn() == turn &&
                    map->getGame() == owner && map->getAssignedPlayer() == player && player &&
                    player->getGame() == owner && clock->getGame() == owner && player->isAlive() &&
                    map->getObjectByName("player") == player && map->getObjectByName("cityClock") == clock &&
                    map->getMapName() == "baldursGate" && map->getActiveSimulationRegion() == identity->area,
                "DOPMER map/player/clock/area binding changed");
        require(actor && typeid(*actor) == typeid(CCreature) && actor->getGame() == owner &&
                    actor->getName() == identity->name && actor->isAlive() && actor->isNpc() &&
                    actor->getAffiliation() == "cityResidents" &&
                    stored<std::string>(actor, "sourceActor") == std::optional<std::string>{identity->sourceActor} &&
                    stored<std::string>(actor, "sourceArea") == std::optional<std::string>{identity->area} &&
                    stored<std::string>(actor, "simulationRegion") == std::optional<std::string>{identity->area} &&
                    stored<std::string>(actor, "sourceCreature") == std::optional<std::string>{"DOPMER"} &&
                    stored<std::string>(actor, "sourceDialogue") == std::optional<std::string>{"DOPMER"},
                "DOPMER source actor changed");
        require(!stored<bool>(map, "plugin_cityFlag_cityCompleted").value_or(false) &&
                    !stored<bool>(map, "plugin_cityFlag_poisonFatal").value_or(false) &&
                    stored<std::string>(map, "plugin_cityCustodyState").value_or("") != "hearing",
                "DOPMER city interaction unavailable");
        auto chapter = stored<int>(map, "plugin_cityPhase").value_or(5);
        require(chapter >= stored<int>(actor, "phaseMin").value_or(5) &&
                    chapter <= stored<int>(actor, "phaseMax").value_or(7),
                "DOPMER source phase changed");
        if (interactive && phase == Phase::Registered) {
            auto a = actor->getCoords(), p = player->getCoords();
            auto dx = static_cast<std::int64_t>(a.x) - p.x, dy = static_cast<std::int64_t>(a.y) - p.y;
            require(a.z == p.z && std::abs(dx) + std::abs(dy) <= 1, "DOPMER dialogue no longer adjacent");
        }
        auto current = map->getObjectByName(identity->name);
        if (phase == Phase::Registered)
            require(current == actor && !oldRef.value && !newRef.value &&
                        !CSevenSunsMerchantDialogue::hasLifetimeOwner(owner, map, actor),
                    "DOPMER old owner changed");
        if (phase == Phase::Preparing)
            require(current == actor &&
                        (!oldRef.value || oldRef.value == std::optional<std::shared_ptr<CGameObject>>{actor}) &&
                        (!newRef.value || newRef.value == std::optional<std::shared_ptr<CGameObject>>{replacement}),
                    "DOPMER staged ownership changed");
        if (phase == Phase::Replacing) {
            require(current == actor || !current || current == replacement, "DOPMER publication superseded");
            if (current != actor)
                require(CSevenSunsMerchantDialogue::retired(owner, map, actor),
                        "DOPMER retirement lifetime anchor was lost");
        }
        if (phase == Phase::Replaced)
            require(oldRef.value == std::optional<std::shared_ptr<CGameObject>>{actor} &&
                        newRef.value == std::optional<std::shared_ptr<CGameObject>>{replacement} && replacement &&
                        CSevenSunsMerchantDialogue::retired(owner, map, actor) &&
                        (current == replacement || (!replacement->isAlive() && !current)),
                    "DOPMER replacement receipt lost its owners");
        definition.check();
        receipt.check();
        globals.check();
        count.check();
        allegiance.check();
        oldRef.check();
        newRef.check();
        if (phase == Phase::Replaced && validateStock)
            CSevenSunsMerchantStock::validateSettled(replacement, row.at("stock"), owner, identity->name,
                                                     identity->area, [this] { check(false); });
    }
    void writeRow(const std::function<void()> &guard) {
        rows["actors"][identity->name] = row;
        auto text = encode(rows);
        require(text.size() <= 65536, "DOPMER receipts exceeded bounded storage");
        receipt.write(std::move(text), guard);
    }
    void preflightGlobals(const Edge &edge) const {
        auto next = source;
        auto put = [&](const char *name, int value) {
            if (!next.contains("GLOBAL"))
                next["GLOBAL"] = json::object();
            next["GLOBAL"][globalKey(name).value_or(name)] = value;
        };
        if (edge.checked)
            put("CheckedSevenSuns", 2);
        if (edge.reveal) {
            put("Doppleganger", 1);
            put("Laola", 1);
        }
        require(next.size() <= 256 && (!next.contains("GLOBAL") || next.at("GLOBAL").size() <= 1024) &&
                    encode(next).size() <= 65536,
                "DOPMER source writes do not fit their admitted store");
        if (firstChoice) {
            auto talks = document(stored<std::string>(map, "plugin_cityTalked"), json::object());
            require(talks.is_object(), "Malformed city talk bookkeeping");
            talks[identity->name] = json{{"label", "Merchant"}, {"creature", "DOPMER"}, {"area", identity->area}};
            require(talks.size() <= 2048 && encode(talks).size() <= 65536, "DOPMER talk capacity before source writes");
            const int generic = stored<int>(actor, "plugin_cityTalkCount").value_or(0);
            require(generic >= 0 && generic < 1000000, "Invalid city generic talk count");
            if (!stored<bool>(map, "plugin_cityHistoryFrozen").value_or(false)) {
                auto choices = document(stored<std::string>(map, "plugin_cityHistory"), json::object());
                auto profile = document(stored<std::string>(map, "plugin_cityStartingProfile"), json::object());
                require(choices.is_object() && profile.is_object(), "Malformed city history/profile");
                for (const auto *key : {"aldeth", "tenya", "eldoth"})
                    if (!choices.contains(key))
                        choices[key] = "unspecified";
                profile["history"] = choices;
                profile["historyFrozen"] = true;
                require(encode(choices).size() <= 65536 && encode(profile).size() <= 65536,
                        "DOPMER history capacity before source writes");
            }
        }
    }
    void writeGlobal(const char *name, int value, const std::function<void()> &guard) {
        if (!source.contains("GLOBAL"))
            source["GLOBAL"] = json::object();
        source["GLOBAL"][globalKey(name).value_or(name)] = value;
        globals.write(encode(source), guard);
        row["globals"] = globalSnapshot();
        writeRow(guard);
    }
    void recordFirstChoice(const std::function<void()> &guard) {
        Field<std::string> talked(map, "plugin_cityTalked");
        auto talks = document(talked.value, json::object());
        require(talks.is_object(), "Malformed city talk bookkeeping");
        talks[identity->name] = json{{"label", "Merchant"}, {"creature", "DOPMER"}, {"area", identity->area}};
        require(talks.size() <= 2048 && encode(talks).size() <= 65536, "DOPMER talk bookkeeping capacity");
        talked.write(encode(talks), guard);
        Field<int> generic(actor, "plugin_cityTalkCount");
        require(generic.value.value_or(0) >= 0 && generic.value.value_or(0) < 1000000,
                "Invalid generic city talk count");
        generic.write(generic.value.value_or(0) + 1, guard);
        Field<bool> frozen(map, "plugin_cityHistoryFrozen");
        if (!frozen.value.value_or(false)) {
            Field<std::string> history(map, "plugin_cityHistory"), profile(map, "plugin_cityStartingProfile");
            auto choices = document(history.value, json::object()), starting = document(profile.value, json::object());
            require(choices.is_object() && starting.is_object(), "Malformed city history/profile");
            for (const auto *key : {"aldeth", "tenya", "eldoth"})
                if (!choices.contains(key))
                    choices[key] = "unspecified";
            starting["history"] = choices;
            starting["historyFrozen"] = true;
            require(encode(choices).size() <= 65536 && encode(starting).size() <= 65536, "City history capacity");
            history.write(encode(choices), guard);
            profile.write(encode(starting), guard);
            frozen.write(true, guard);
        }
    }
};
std::mutex CSevenSunsMerchantDialogue::State::mutex;
std::map<const CMap *, CSevenSunsMerchantDialogue::State *> CSevenSunsMerchantDialogue::State::sessions;

CSevenSunsMerchantDialogue::CSevenSunsMerchantDialogue(std::unique_ptr<State> value) : state(std::move(value)) {}
CSevenSunsMerchantDialogue::CSevenSunsMerchantDialogue(std::string reason, std::string lineage, int count, int revision)
    : refusal(std::move(reason)), refusedLineage(std::move(lineage)), refusedCount(count), refusedRevision(revision) {}
CSevenSunsMerchantDialogue::~CSevenSunsMerchantDialogue() = default;
bool CSevenSunsMerchantDialogue::isSupported() { return CSevenSunsMerchantStock::isSupported(); }
bool CSevenSunsMerchantDialogue::isSettledReplacement(const std::shared_ptr<CGame> &game,
                                                      const std::shared_ptr<CMap> &map,
                                                      const std::shared_ptr<CCreature> &actor,
                                                      const std::function<void()> &requireCurrent) {
    if (!game || !map || map->getMapName() != "baldursGate" || !actor ||
        actor->getTypeId() != "citySevenSunsRevealedDoppss")
        return false;
    require(requireCurrent != nullptr, "Seven Suns defeat authority needs its current owner guard");
    requireCurrent();
    const auto *identity = lineage(actor->getName());
    require(identity && typeid(*actor) == typeid(CCreature) && game->getMap() == map && map->getGame() == game &&
                actor->getGame() == game && map->getObjectByName(identity->name) == actor,
            "Seven Suns dedicated defeat role lost its exact registered actor");
    auto clock = map->getObjectByName("cityClock");
    require(clock && clock->getGame() == game && definitionAvailable(clock),
            "Seven Suns dedicated defeat role lost its source clock");
    auto oldRef =
        stored<std::shared_ptr<CGameObject>>(clock, std::string("plugin_citySevenSunsMerchantOld_") + identity->name);
    auto oldActor = oldRef ? std::dynamic_pointer_cast<CCreature>(*oldRef) : nullptr;
    require(oldActor && oldActor != actor, "Seven Suns dedicated defeat role lost its retained original");
    State value(game, clock, oldActor, identity, false, requireCurrent);
    require(value.phase == State::Phase::Replaced && value.replacement == actor &&
                value.row.at("status").get<std::string>() == "replaced",
            "Seven Suns dedicated defeat role lacks its committed replacement receipt");
    value.check();
    requireCurrent();
    return true;
}
int CSevenSunsMerchantDialogue::readInteger(const json &value) { return integer(value); }
bool CSevenSunsMerchantDialogue::combatOwned(const std::shared_ptr<CCreature> &actor) {
    return CFightHandler::hasActiveCombatClaim(actor);
}
std::uint64_t CSevenSunsMerchantDialogue::regionEpoch(const std::shared_ptr<CGame> &game,
                                                      const std::shared_ptr<CMap> &map) {
    return game->getSceneManager()->sceneRegionRevision(map);
}
bool CSevenSunsMerchantDialogue::retired(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                         const std::shared_ptr<CCreature> &actor) {
    return game->getSceneManager()->isSceneObjectRetired(map, actor);
}
bool CSevenSunsMerchantDialogue::hasLifetimeOwner(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                                  const std::shared_ptr<CCreature> &actor) {
    return game->getSceneManager()->containsSceneRetiredObject(map, actor);
}
bool CSevenSunsMerchantDialogue::unowned(const std::shared_ptr<CGame> &game, const std::shared_ptr<CCreature> &actor) {
    return game->getSceneManager()->isSceneObjectUnowned(actor);
}
void CSevenSunsMerchantDialogue::publish(const std::shared_ptr<CGame> &game, const std::shared_ptr<CMap> &map,
                                         const std::shared_ptr<CCreature> &oldActor,
                                         const std::shared_ptr<CCreature> &newActor,
                                         const std::function<void()> &guard) {
    game->getSceneManager()->replaceObjectWithoutEvents(game, map, oldActor, newActor, guard);
}

std::unique_ptr<CSevenSunsMerchantDialogue> CSevenSunsMerchantDialogue::begin(std::weak_ptr<CGame> weakGame,
                                                                              std::shared_ptr<CGameObject> clock,
                                                                              std::shared_ptr<CCreature> actor,
                                                                              std::function<void()> requireCaller) {
    require(vstd::event_loop<>::instance()->isMainThread(), "DOPMER requires engine owner thread");
    if (requireCaller)
        requireCaller();
    auto game = weakGame.lock();
    auto map = game ? game->getMap() : nullptr;
    auto identity = actor ? lineage(actor->getName()) : nullptr;
    require(game && map && typeid(*map) == typeid(CMap) && identity && clock &&
                map->getObjectByName("cityClock") == clock && clock->getGame() == game,
            "Wrong DOPMER source binding");
    auto refuse = [identity](std::string reason, int count = 0, int revision = 0) {
        return std::unique_ptr<CSevenSunsMerchantDialogue>(
            new CSevenSunsMerchantDialogue(std::move(reason), identity->name, count, revision));
    };
    if (!definitionAvailable(clock) || !isSupported())
        return refuse("conversionUnavailable");
    {
        std::lock_guard lock(State::mutex);
        if (auto found = State::sessions.find(map.get()); found != State::sessions.end()) {
            if (found->second->mutating)
                found->second->poisoned = true;
            throw std::runtime_error("DOPMER reentry already owns this city");
        }
    }
    if (combatOwned(actor))
        return refuse("activeCombat");
    auto lease = map->tryBeginUnsafeOperation();
    if (!lease)
        return refuse("admissionClosed");
    auto value = std::make_unique<State>(game, clock, actor, identity, true, std::move(requireCaller));
    try {
        value->check();
    } catch (...) {
        lease->finish();
        throw;
    }
    const int n = value->count.value.value_or(0), revision = integer(value->row.at("revision"));
    if (!value->count.value && stored<int>(actor, "plugin_cityTalkCount").value_or(0) != 0) {
        lease->finish();
        return refuse("legacyCountUnknown", n, revision);
    }
    if (value->phase == State::Phase::Replaced) {
        lease->finish();
        value->terminal = true;
        return std::unique_ptr<CSevenSunsMerchantDialogue>(new CSevenSunsMerchantDialogue(std::move(value)));
    }
    if (n >= 3) {
        lease->finish();
        return refuse("noAuditedEntry", n, revision);
    }
    if (revision >= 999999) {
        lease->finish();
        return refuse("revisionLimit", n, revision);
    }
    value->claim();
    value->mutating = true;
    auto check = [&] {
        value->check();
        require(lease->isSaveAdmissionHealthy(), "DOPMER initiation admission was quarantined");
    };
    try {
        auto barrier = game->getObjectHandler()->beginDefeatConstruction(check);
        ActorSnapshot original(actor), hero(value->player);
        value->row["status"] = "pending";
        value->writeRow(check);
        value->count.write(n + 1, check);
        value->row["sourceTalkCount"] = n + 1;
        value->row["entry"] = n == 0 ? 0 : n == 1 ? 7 : 10;
        value->row["cursor"] = value->row.at("entry");
        value->row["lastEdge"] = -1;
        value->row["edges"] = json::array();
        value->row["revision"] = revision + 1;
        value->row["status"] = "active";
        value->row["globals"] = value->globalSnapshot();
        value->writeRow(check);
        original.check();
        hero.check();
        check();
        value->mutating = false;
        lease->finish();
    } catch (...) {
        value->poisoned = true;
        value->mutating = false;
        lease->quarantine();
        throw;
    }
    return std::unique_ptr<CSevenSunsMerchantDialogue>(new CSevenSunsMerchantDialogue(std::move(value)));
}
void CSevenSunsMerchantDialogue::requireCurrent() const {
    if (state && !state->terminal)
        state->check();
}
json CSevenSunsMerchantDialogue::view() const {
    if (!state)
        return json{{"status", "refused"},         {"reason", refusal},
                    {"capabilityVersion", 1},      {"dialogue", "DOPMER"},
                    {"lineage", refusedLineage},   {"state", -1},
                    {"revision", refusedRevision}, {"sourceTalkCount", refusedCount},
                    {"choices", json::array()},    {"automaticEdge", nullptr},
                    {"revealRequested", false},    {"attackRevealSupported", false}};
    requireCurrent();
    json choices = json::array(), automatic = nullptr;
    int cursor = integer(state->row.at("cursor"));
    if (!state->terminal)
        for (const auto &edge : Edges)
            if (edge.from == cursor) {
                if (edge.terminal)
                    automatic = edge.index;
                else
                    choices[choices.size()] = edge.index;
            }
    bool reveal = false;
    int last = integer(state->row.at("lastEdge"));
    for (const auto &edge : Edges)
        if (edge.index == last)
            reveal = edge.reveal;
    return json{{"status", state->phase == State::Phase::Replaced ? "replaced"
                           : state->terminal                      ? "closed"
                                                                  : "ready"},
                {"reason", ""},
                {"capabilityVersion", 1},
                {"dialogue", "DOPMER"},
                {"lineage", state->identity->name},
                {"state", cursor},
                {"revision", state->row.at("revision")},
                {"sourceTalkCount", state->row.at("sourceTalkCount")},
                {"choices", choices},
                {"automaticEdge", automatic},
                {"revealRequested", reveal},
                {"attackRevealSupported", false}};
}
json CSevenSunsMerchantDialogue::advance(int revision, int edgeIndex) {
    require(state && !state->terminal, "DOPMER has no active conversation");
    if (state->mutating) {
        state->poisoned = true;
        throw std::runtime_error("Reentrant DOPMER edge");
    }
    state->check();
    require(integer(state->row.at("revision")) == revision && revision < 999999, "Stale DOPMER revision");
    const Edge *edge = nullptr;
    for (const auto &candidate : Edges)
        if (candidate.index == edgeIndex && candidate.from == integer(state->row.at("cursor")))
            edge = &candidate;
    require(edge, "Unsupported DOPMER source edge");
    state->preflightGlobals(*edge);
    auto lease = state->map->tryBeginUnsafeOperation();
    require(lease.has_value(), "DOPMER edge admission closed");
    auto game = state->game.lock();
    require(game != nullptr, "DOPMER game expired");
    state->mutating = true;
    auto check = [&] {
        state->check();
        require(lease->isSaveAdmissionHealthy(), "DOPMER edge admission quarantined");
    };
    try {
        auto barrier = game->getObjectHandler()->beginDefeatConstruction(check);
        ActorSnapshot old(state->actor), hero(state->player);
        state->row["status"] = "pending";
        state->writeRow(check);
        if (edge->checked)
            state->writeGlobal("CheckedSevenSuns", 2, check);
        if (edge->reveal) {
            state->writeGlobal("Doppleganger", 1, check);
            state->writeGlobal("Laola", 1, check);
        }
        if (state->firstChoice)
            state->recordFirstChoice(check);
        state->row["edges"][state->row.at("edges").size()] = edgeIndex;
        require(state->row.at("edges").size() <= 4, "DOPMER exceeded finite source path");
        state->row["lastEdge"] = edgeIndex;
        state->row["cursor"] = edge->to;
        state->row["revision"] = revision + 1;
        state->row["status"] = edge->terminal ? "closed" : "active";
        state->writeRow(check);
        old.check();
        hero.check();
        check();
        state->firstChoice = false;
        state->mutating = false;
        state->terminal = edge->terminal;
        lease->finish();
        return view();
    } catch (...) {
        state->poisoned = true;
        state->mutating = false;
        lease->quarantine();
        throw;
    }
}
json CSevenSunsMerchantDialogue::close() {
    require(!state || !state->mutating, "Cannot close admitted DOPMER operation");
    if (!state)
        return view();
    state->terminal = true;
    return view();
}

json CSevenSunsMerchantDialogue::settle(std::weak_ptr<CGame> weakGame, std::shared_ptr<CGameObject> clock,
                                        std::function<void()> requireCaller) {
    require(vstd::event_loop<>::instance()->isMainThread(), "DOPMER settlement requires engine owner thread");
    if (requireCaller)
        requireCaller();
    auto game = weakGame.lock();
    auto map = game ? game->getMap() : nullptr;
    require(game && map && typeid(*map) == typeid(CMap) && clock && map->getObjectByName("cityClock") == clock &&
                clock->getGame() == game,
            "Wrong DOPMER settlement owner");
    const auto area = map->getActiveSimulationRegion();
    const int turn = map->getTurn();
    int checked = 0, replaced = 0;
    bool retry = false;
    auto result = [&] {
        json result{{"status", retry ? "retry" : "settled"},
                    {"capabilityVersion", 1},
                    {"checked", checked},
                    {"replaced", replaced},
                    {"turn", turn},
                    {"area", area},
                    {"attackRevealSupported", false}};
        CPlaytestTrace::addMapContext(result, map);
        CPlaytestTrace::record("seven_suns_merchants_settle", result);
        return result;
    };
    if (!definitionAvailable(clock) || !isSupported()) {
        retry = true;
        return result();
    }
    {
        std::lock_guard lock(State::mutex);
        if (auto found = State::sessions.find(map.get()); found != State::sessions.end()) {
            if (found->second->mutating)
                found->second->poisoned = true;
            retry = true;
            return result();
        }
    }
    std::array<std::shared_ptr<CCreature>, 4> candidates;
    bool claimed = false;
    for (const auto &identity : Lineages) {
        ++checked;
        if (area != identity.area)
            continue;
        auto candidate = std::dynamic_pointer_cast<CCreature>(map->getObjectByName(identity.name));
        auto old = stored<std::shared_ptr<CGameObject>>(clock, std::string("plugin_citySevenSunsMerchantOld_") +
                                                                   identity.name);
        if (old)
            candidate = std::dynamic_pointer_cast<CCreature>(*old);
        candidates[static_cast<std::size_t>(checked - 1)] = candidate;
        claimed = claimed || (candidate && combatOwned(candidate));
    }
    if (claimed) {
        retry = true;
        return result();
    }
    for (std::size_t index = 0; index < Lineages.size(); ++index) {
        const auto &identity = Lineages[index];
        auto candidate = candidates[index];
        if (!candidate)
            continue;
        if (combatOwned(candidate)) {
            retry = true;
            continue;
        }
        if (!stored<int>(candidate, CountKey) && stored<int>(candidate, "plugin_cityTalkCount").value_or(0) != 0) {
            retry = true;
            continue;
        }
        const int chapter = stored<int>(map, "plugin_cityPhase").value_or(5);
        if (chapter < stored<int>(candidate, "phaseMin").value_or(5) ||
            chapter > stored<int>(candidate, "phaseMax").value_or(7))
            continue;
        auto lease = map->tryBeginUnsafeOperation();
        if (!lease) {
            retry = true;
            continue;
        }
        auto value = std::make_unique<State>(game, clock, candidate, &identity, false, requireCaller);
        if (value->phase == State::Phase::Replaced) {
            value->check();
            lease->finish();
            continue;
        }
        try {
            value->check();
        } catch (...) {
            lease->finish();
            throw;
        }
        if (value->global("Doppleganger") != 1) {
            lease->finish();
            continue;
        }
        if (integer(value->row.at("revision")) >= 999999) {
            lease->finish();
            retry = true;
            continue;
        }
        if (stored<int>(candidate, "sourceAllegiance") != std::optional<int>{128} ||
            !stored<bool>(candidate, "plugin_cityHooksInstalled").value_or(false)) {
            lease->finish();
            retry = true;
            continue;
        }
        value->claim();
        value->mutating = true;
        auto check = [&] {
            value->check();
            require(!combatOwned(candidate) && lease->isSaveAdmissionHealthy(), "DOPMER settlement ownership changed");
        };
        try {
            auto barrier = game->getObjectHandler()->beginDefeatConstruction(check);
            ActorSnapshot original(candidate), hero(value->player);
            check();
            value->row["status"] = "pending";
            value->writeRow(check);
            value->phase = State::Phase::Preparing;
            value->oldRef.write(candidate, check);
            auto prepared = CSevenSunsMerchantStock::prepare(game, identity.name, identity.area, check);
            check();
            require(prepared.actor && prepared.actor != candidate && prepared.actor != value->player &&
                        typeid(*prepared.actor) == typeid(CCreature) && unowned(game, prepared.actor),
                    "DOPMER factory returned an aliased owner");
            value->replacement = prepared.actor;
            prepared.actor->setName(identity.name);
            check();
            prepared.actor->relocateWithoutMoveHooks(candidate->getCoords());
            check();
            CSevenSunsMerchantStock::validatePrepared(prepared, game, identity.name, identity.area, check);
            check();
            require(encode(prepared.receipt).size() <= 16384, "DOPMER stock receipt exceeds its bound");
            value->newRef.write(prepared.actor, check);
            value->row["stock"] = prepared.receipt;
            value->writeRow(check);
            value->phase = State::Phase::Replacing;
            publish(game, map, candidate, prepared.actor, check);
            value->phase = State::Phase::Replaced;
            check();
            CSevenSunsMerchantStock::validatePrepared(prepared, game, identity.name, identity.area, check);
            check();
            original.check();
            hero.check();
            value->row["status"] = "replaced";
            value->row["settledTurn"] = turn;
            value->row["predicate"] = json{{"Doppleganger", 1}, {"sourceAllegiance", 128}, {"area", identity.area}};
            value->row["globals"] = value->globalSnapshot();
            value->row["revision"] = integer(value->row.at("revision")) + 1;
            value->writeRow(check);
            check();
            value->mutating = false;
            lease->finish();
            ++replaced;
        } catch (...) {
            value->poisoned = true;
            value->mutating = false;
            lease->quarantine();
            throw;
        }
    }
    return result();
}
