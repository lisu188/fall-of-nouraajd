#include "stats.h"

#include <sstream>
#include <string>

Stats::Stats() {}

void Stats::setMain(const char *stat) {
    mainS = stat ? stat : "";
    if (!stat || !*stat) {
        main = &strength;
        return;
    }

    switch (stat[0]) {
    case 'A':
        main = &agility;
        break;
    case 'I':
        main = &intelligence;
        break;
    case 'S':
    default:
        main = &strength;
        break;
    }
}

int Stats::getMain() { return main ? *main : 0; }

void Stats::addBonus(Stats stats) {
    strength += stats.getStrength();
    stamina += stats.getStamina();
    agility += stats.getAgility();
    intelligence += stats.getIntelligence();

    armor += stats.getArmor();
    block += stats.getBlock();

    dmgMin += stats.getDmgMin();
    dmgMax += stats.getDmgMax();
    hit += stats.getHit();
    crit += stats.getCrit();

    fireResist += stats.getFireResist();
    thunderResist += stats.getThunderResist();
    frostResist += stats.getFrostResist();
    normalResist += stats.getNormalResist();

    damage += stats.getDamage();
    attack += stats.getAttack();
}

void Stats::removeBonus(Stats stats) {
    strength -= stats.getStrength();
    stamina -= stats.getStamina();
    agility -= stats.getAgility();
    intelligence -= stats.getIntelligence();

    armor -= stats.getArmor();
    block -= stats.getBlock();

    dmgMin -= stats.getDmgMin();
    dmgMax -= stats.getDmgMax();
    hit -= stats.getHit();
    crit -= stats.getCrit();

    fireResist -= stats.getFireResist();
    thunderResist -= stats.getThunderResist();
    frostResist -= stats.getFrostResist();
    normalResist -= stats.getNormalResist();

    damage -= stats.getDamage();
    attack -= stats.getAttack();
}

































const char *Stats::getText(int level) {
    static std::string text;
    std::ostringstream stream;
    stream << "Level " << level << " S:" << getStrength() << " A:" << getAgility() << " I:" << getIntelligence()
           << " St:" << getStamina();
    text = stream.str();
    return text.c_str();
}

void Stats::loadFromJson(Json::Value statConfig) {
    if (!statConfig.isObject())
        return;
    strength = statConfig.get("strength", strength).asInt();
    stamina = statConfig.get("stamina", stamina).asInt();
    agility = statConfig.get("agility", agility).asInt();
    intelligence = statConfig.get("intelligence", intelligence).asInt();
    armor = statConfig.get("armor", armor).asInt();
    block = statConfig.get("block", block).asInt();
    dmgMin = statConfig.get("dmgMin", dmgMin).asInt();
    dmgMax = statConfig.get("dmgMax", dmgMax).asInt();
    hit = statConfig.get("hit", hit).asInt();
    crit = statConfig.get("crit", crit).asInt();
    fireResist = statConfig.get("fireResist", fireResist).asInt();
    thunderResist = statConfig.get("thunderResist", thunderResist).asInt();
    frostResist = statConfig.get("frostResist", frostResist).asInt();
    normalResist = statConfig.get("normalResist", normalResist).asInt();
    shadowResist = statConfig.get("shadowResist", shadowResist).asInt();
    damage = statConfig.get("damage", damage).asInt();
    attack = statConfig.get("attack", attack).asInt();
    if (statConfig.isMember("main"))
        setMain(statConfig["main"].asString().c_str());
}

Json::Value Stats::saveToJson() {
    Json::Value config;
    config["strength"] = strength;
    config["stamina"] = stamina;
    config["agility"] = agility;
    config["intelligence"] = intelligence;
    config["armor"] = armor;
    config["block"] = block;
    config["dmgMin"] = dmgMin;
    config["dmgMax"] = dmgMax;
    config["hit"] = hit;
    config["crit"] = crit;
    config["fireResist"] = fireResist;
    config["thunderResist"] = thunderResist;
    config["frostResist"] = frostResist;
    config["normalResist"] = normalResist;
    config["shadowResist"] = shadowResist;
    config["damage"] = damage;
    config["attack"] = attack;
    config["main"] = mainS;
    return config;
}






Stats::Stats(const Stats &other) : QObject() {
    strength = other.strength;
    stamina = other.stamina;
    agility = other.agility;
    intelligence = other.intelligence;
    armor = other.armor;
    block = other.block;
    dmgMin = other.dmgMin;
    dmgMax = other.dmgMax;
    hit = other.hit;
    crit = other.crit;
    fireResist = other.fireResist;
    thunderResist = other.thunderResist;
    frostResist = other.frostResist;
    normalResist = other.normalResist;
    damage = other.damage;
    attack = other.attack;
    shadowResist = other.shadowResist;
    setMain(other.mainS.c_str());
}

Damage::Damage() {}
Damage::Damage(const Damage &other) : QObject() {
    fire = other.fire;
    thunder = other.thunder;
    frost = other.frost;
    normal = other.normal;
    shadow = other.shadow;
}
