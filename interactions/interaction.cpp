#include "interaction.h"

#include <creatures/player.h>

#include <view/gamescene.h>
#include <view/gameview.h>

#include <view/playerstatsview.h>
#include <view/fightview.h>

#include <items/armor.h>
#include <items/weapon.h>
#include <stats/stats.h>
#include <stats/damage.h>
#include <configuration/configurationprovider.h>

#include <QDebug>
#include <list>
#include <creatures/creature.h>

std::unordered_map<std::string, std::function<void(Creature *, Creature *)>> Interaction::actions = {
    {"Attack", Attack},
    {"ElemStaff", ElemStaff},
    {"DoubleAttack", DoubleAttack},
    {"SneakAttack", SneakAttack},
    {"Strike", Strike},
    {"ArmorOfEndlessWinter", ArmorOfEndlessWinter},
    {"ChaosBlast", ChaosBlast},
    {"Devour", Devour},
    {"FrostBolt", FrostBolt},
    {"MagicMissile", MagicMissile},
    {"ShadowBolt", ShadowBolt},
    {"Mutilation", Mutilation},
    {"LethalPoison", LethalPoison},
    {"Backstab", Backstab},
    {"Bloodlash", Bloodlash},
    {"DeathStrike", DeathStrike},
    {"Barrier", Barrier},
    {"BloodThirst", BloodThirst}};

Interaction::Interaction(std::string name) {
    className = name;
    MapObject::className = name;
    loadFromJson((*ConfigurationProvider::getConfig("config/interactions.json"))[name]);
}

void Interaction::loadFromJson(Json::Value config) {
    if (config.isArray() && config.size() >= 3) {
        moveTo(config[(unsigned int)0].asInt(), config[(unsigned int)1].asInt(), config[(unsigned int)2].asInt(), true);
        return;
    }
    manaCost = config.get("manaCost", 0).asInt();
    effect = config.get("effect", "").asString();
    std::string anim = config.get("anim", "").asString();
    if (anim.compare("") != 0) {
        setAnimation(anim);
    }
}

void Interaction::onAction(Creature *first, Creature *second) {
    qDebug() << first->className.c_str() << "used" << this->className.c_str() << "against" << second->className.c_str();
    if (actions[className]) {
        actions[className](first, second);
    } else if (!effect.empty()) {
        Json::Value config = (*ConfigurationProvider::getConfig("config/effects.json"))[effect];
        Creature *target = config.get("buff", false).asBool() ? first : second;
        target->addEffect(effect, first);
    }
}

int Interaction::getManaCost() { return manaCost; }

Interaction *Interaction::getInteraction(std::string name) {
    if (name.compare("") == 0) {
        return 0;
    }
    return new Interaction(name);
}

void Interaction::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    Player *player = GameScene::getPlayer();
    if (player->getFightList()->size() == 0) {
        return;
    }
    if (manaCost > player->getMana()) {
        return;
    }
    Creature *creature = FightView::selected;
    if (!creature) {
        return;
    }
    player->performAction(this, creature);
}

void Attack(Creature *first, Creature *second) {
    int dmg = first->getDmg();
    if (dmg) {
        second->hurt(dmg);
        Weapon *weapon = first->getWeapon();
        if (weapon) {
            Interaction *interaction = weapon->getInteraction();
            if (interaction) {
                interaction->onAction(first, second);
            }
        }
    }
}

void ElemStaff(Creature *first, Creature *second) {
    Damage damage;
    damage.setFire(1);
    damage.setFrost(1);
    damage.setThunder(1);
    second->hurt(damage);
}

void DoubleAttack(Creature *first, Creature *second) {
    Attack(first, second);
    Attack(first, second);
}

void SneakAttack(Creature *first, Creature *second) {
    Attack(first, second);
    if (rand() % 100 > (100 - second->getHpRatio())) {
        if (second->isAlive()) {
            Attack(first, second);
        }
    }
}

void Strike(Creature *first, Creature *second) {
    if (first->getWeapon()) {
        int dmg = first->getDmg();
        if (dmg) {
            second->hurt(dmg + first->getStats()->getDamage());
        }
    }
}

void ArmorOfEndlessWinter(Creature *first, Creature *second) { first->addEffect("ArmorOfEndlessWinterEffect", first); }

void ChaosBlast(Creature *first, Creature *second) {
    Damage damage;
    damage.setFire(first->getMana() / 2);
    damage.setThunder(first->getMana() / 2);
    second->hurt(damage);
}

void Devour(Creature *first, Creature *second) {
    int crit = first->getStats()->getCrit();
    first->getStats()->setCrit(0);
    int dmg = first->getDmg();
    if (dmg) {
        second->hurt(dmg);
        first->heal(dmg * 0.75);
    }
    first->getStats()->setCrit(crit);
}

void FrostBolt(Creature *first, Creature *second) {
    Attack(first, second);
    Damage damage;
    damage.setFrost(first->getStats()->getIntelligence() * 75.0 / 100.0);
    second->hurt(damage);
    // change to ice
}

void MagicMissile(Creature *first, Creature *second) {
    int dmg = 0;
    for (int i = 0; i < first->getMana() / 10 + 1; i++) {
        dmg += rand() % 4 + 1;
    }
    second->hurt(dmg);
}

void ShadowBolt(Creature *first, Creature *second) {
    Damage damage;
    damage.setShadow(first->getDmg() * 2.25);
    second->hurt(damage);
    if (rand() % 2 == 0) {
        damage.setShadow(first->getWeapon()->getStats()->getDamage());
        second->addEffect("AbyssalShadowsEffect", first);
    }
}

void Mutilation(Creature *first, Creature *second) { second->addEffect("MutilationEffect", first); }

void LethalPoison(Creature *first, Creature *second) { second->addEffect("LethalPoisonEffect", first); }

void Backstab(Creature *first, Creature *second) { second->hurt(first->getDmg() * 2); }

void Bloodlash(Creature *first, Creature *second) { second->addEffect("BloodlashEffect", first); }

void DeathStrike(Creature *first, Creature *second) { Attack(first, second); }

void Barrier(Creature *first, Creature *second) { first->addEffect("BarrierEffect", first); }

void BloodThirst(Creature *first, Creature *second) {
    int damage = first->getDmg();
    second->hurt(damage);
    first->heal(damage);
}

#include <QDebug>
#include <creatures/creature.h>

std::unordered_map<std::string, std::function<bool(Effect *effects, Creature *)>> Effect::effects{
    {"Stun", &Stun},
    {"EndlessPainEffect", &EndlessPainEffect},
    {"MutilationEffect", &MutilationEffect},
    {"AbyssalShadowsEffect", &AbyssalShadowsEffect},
    {"ArmorOfEndlessWinterEffect", &ArmorOfEndlessWinterEffect},
    {"LethalPoisonEffect", &LethalPoisonEffect},
    {"ChloroformEffect", &ChloroformEffect},
    {"BloodlashEffect", &BloodlashEffect},
    {"BarrierEffect", &BarrierEffect}};

Effect::Effect(std::string type, Creature *caster) : caster(caster) {
    bonus = 0;
    className = type;
    Json::Value config = (*ConfigurationProvider::getConfig("config/effects.json"))[type];
    timeLeft = timeTotal = config.get("duration", 1).asInt();
}

int Effect::getTimeLeft() { return timeLeft; }

int Effect::getTimeTotal() { return timeTotal; }

Creature *Effect::getCaster() { return caster; }

bool Effect::apply(Creature *creature) {
    if (bonus)
        if (timeTotal == timeLeft) {
            creature->getStats()->addBonus(*bonus);
        }
    timeLeft--;
    if (timeLeft == 0) {
        if (bonus) {
            creature->getStats()->removeBonus(*bonus);
        }
        return false;
    }
    return effects[className](this, creature);
}

Stats *Effect::getBonus() { return bonus; }

void Effect::setBonus(Stats *value) { bonus = value; }

bool Stun(Effect *effect, Creature *creature) { return true; }

bool EndlessPainEffect(Effect *effect, Creature *creature) {
    creature->hurt(effect->getCaster()->getDmg() * 15.0 / 100.0);
    return true;
}

bool AbyssalShadowsEffect(Effect *effect, Creature *creature) {
    if (effect->getTimeLeft() > 1) {
        Damage tmp;
        tmp.setShadow(effect->getCaster()->getDmg() * 45.0 / 100.0);
        creature->hurt(tmp);
    } else {
        Damage tmp;
        tmp.setShadow(effect->getCaster()->getDmg());
        creature->hurt(tmp);
    }
    return false;
}

bool ArmorOfEndlessWinterEffect(Effect *effect, Creature *creature) {
    creature->healProc(20);
    return false; // must implement ban to other skills
}

bool MutilationEffect(Effect *effect, Creature *creature) {
    creature->hurt(effect->getCaster()->getStats()->getAgility() * 0.25);
    return false;
}

bool LethalPoisonEffect(Effect *effect, Creature *creature) {
    creature->hurt(effect->getCaster()->getDmg() * 4.0 / 6.0);
    return false;
}

bool ChloroformEffect(Effect *effect, Creature *creature) {
    return creature->getHpRatio() > 25; // must discuss going to sleep again
}

bool BloodlashEffect(Effect *effect, Creature *creature) {
    creature->hurt(effect->getCaster()->getDmg() * 0.75);
    return false;
}

bool BarrierEffect(Effect *effect, Creature *creature) { return false; }

void Interaction::onEnter() {
    Player *player = GameScene::getPlayer();
    if (!player)
        return;
    if (getMap())
        getMap()->removeObject(this);
    player->addAction(this);
    player->updateViews();
}

void Interaction::onMove() {}

Json::Value Interaction::saveToJson() {
    Json::Value config(Json::arrayValue);
    config.append(getPosX());
    config.append(getPosY());
    config.append(getPosZ());
    return config;
}

bool Interaction::canSave() { return true; }
