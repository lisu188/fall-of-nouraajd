#include "interaction.h"

#include <src/player.h>

#include <src/gamescene.h>
#include <src/gameview.h>

#include <src/playerstatsview.h>
#include <src/gamepanel.h>

#include <src/item.h>
#include <src/item.h>
#include <src/stats.h>
#include <src/stats.h>
#include <src/CConfigurationProvider.h>

#include <QDebug>
#include <list>
#include <src/creature.h>




void Interaction::loadFromJson(std::string name) {
    typeName = name;
    Json::Value config = (*CConfigurationProvider::getConfig("config/object.json"))[name];
    tooltip = config.get("tooltip", name).asString();
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
    qDebug() << first->typeName.c_str() << "used" << this->typeName.c_str() << "against" << second->typeName.c_str();
    performAction(first, second);
    if (!effect.empty()) {
        Effect *created = new Effect(effect, first, second);
        if (configureEffect(created)) {
            second->addEffect(created);
        } else {
            delete created;
        }
    }
}

int Interaction::getManaCost() { return manaCost; }

void Interaction::mousePressEvent(QGraphicsSceneMouseEvent *event) {
    GameScene *gameScene = dynamic_cast<GameScene *>(this->scene());
    Player *player = gameScene ? gameScene->getPlayer() : NULL;
    if (player->getFightList()->size() == 0) {
        return;
    }
    if (manaCost > player->getMana()) {
        return;
    }
    Creature *creature = FightPanel::selected;
    if (!creature) {
        return;
    }
    player->performAction(this, creature);
}

#include <QDebug>
#include <src/creature.h>

std::unordered_map<std::string, std::function<bool(Effect *effects, Creature *)>> Effect::effects{
    {"Stun", &StunEffect},
    {"EndlessPainEffect", &EndlessPainEffect},
    {"MutilationEffect", &MutilationEffect},
    {"AbyssalShadowsEffect", &AbyssalShadowsEffect},
    {"ArmorOfEndlessWinterEffect", &ArmorOfEndlessWinterEffect},
    {"LethalPoisonEffect", &LethalPoisonEffect},
    {"ChloroformEffect", &ChloroformEffect},
    {"BloodlashEffect", &BloodlashEffect},
    {"BarrierEffect", &BarrierEffect}};

Effect::Effect(std::string type, Creature *caster, Creature *victim) : caster(caster), victim(victim) {
    bonus = 0;
    className = type;
    Json::Value config = (*CConfigurationProvider::getConfig("config/effects.json"))[type];
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

bool StunEffect(Effect *effect, Creature *creature) { return true; }

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
    GameScene *gameScene = dynamic_cast<GameScene *>(this->scene());
    Player *player = gameScene ? gameScene->getPlayer() : NULL;
    if (!player)
        return;
    if (getMap())
        getMap()->removeObject(this);
    player->addAction(this);
    player->updateViews();
}

void Interaction::onMove() {}





Interaction::Interaction() : MapObject(0, 0, 0, 2), manaCost(0) {}
Interaction::Interaction(const Interaction &interaction) : Interaction() { loadFromJson(interaction.typeName); }
bool Interaction::compare(MapObject *item) { return MapObject::compare(item); }
Json::Value Effect::saveToJson() {
    Json::Value config;
    config["type"] = className;
    config["timeLeft"] = timeLeft;
    config["timeTotal"] = timeTotal;
    return config;
}

Creature *Effect::getVictim() { return victim; }

// Python interaction classes override these (#245); the C++ base does nothing itself.
void Interaction::performAction(Creature *, Creature *) {}

bool Interaction::configureEffect(Effect *) { return true; }
