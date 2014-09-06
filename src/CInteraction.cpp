#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "CGamePanel.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CInteraction.h"
#include "CScriptEngine.h"
#include <QDebug>
#include <QGraphicsSceneMouseEvent>

namespace {
QJsonObject effectConfiguration(QString type) {
  QJsonObject effects =
      CConfigurationProvider::getConfig("config/objects/effects.json")
          .toObject();
  if (type == "StunEffect" && !effects.contains(type)) {
    type = "Stun";
  }
  return effects[type].toObject();
}
} // namespace

CInteraction::CInteraction() : manaCost(0) {
  setVisible(false);
  statsView.setParentItem(this);
  statsView.setPos(0, 50);
}
CInteraction::CInteraction(const CInteraction &interaction) : CInteraction() {
  manaCost = interaction.manaCost;
  effect = interaction.effect;
  typeName = interaction.typeName;
}
void CInteraction::onAction(CCreature *first, CCreature *second) {
  qDebug() << first->typeName << "used" << typeName << "against"
           << second->typeName;
  performAction(first, second);
  if (!effect.isEmpty()) {
    CCreature *victim =
        effectConfiguration(effect)["buff"].toBool() ? first : second;
    Effect *active = new Effect(effect, first, victim);
    if (configureEffect(active)) {
      victim->addEffect(active);
    } else {
      delete active;
    }
  }
}
void CInteraction::performAction(CCreature *first, CCreature *second) {
  PY_UNSAFE(boost::python::object function =
                getMap()->getEngine()->getObject(typeName);
            function(boost::python::ptr(first), boost::python::ptr(second));)
}
bool CInteraction::configureEffect(Effect *) { return true; }
void CInteraction::onEnter() { CMapObject::onEnter(); }
void CInteraction::onMove() { CMapObject::onMove(); }
bool CInteraction::compare(CMapObject *item) {
  return CMapObject::compare(item);
}
void CInteraction::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  CPlayer *player = map->getPlayer();
  if (!player || player->getFightList()->empty() ||
      manaCost > player->getMana() || !CFightPanel::selected) {
    event->ignore();
    return;
  }
  player->performAction(this, CFightPanel::selected);
  event->accept();
}
int CInteraction::getManaCost() { return manaCost; }

std::map<QString, std::function<bool(Effect *, CCreature *)>> Effect::effects =
    {{"Stun", StunEffect},
     {"StunEffect", StunEffect},
     {"EndlessPainEffect", EndlessPainEffect},
     {"AbyssalShadowsEffect", AbyssalShadowsEffect},
     {"ArmorOfEndlessWinterEffect", ArmorOfEndlessWinterEffect},
     {"MutilationEffect", MutilationEffect},
     {"LethalPoisonEffect", LethalPoisonEffect},
     {"ChloroformEffect", ChloroformEffect},
     {"BloodlashEffect", BloodlashEffect},
     {"BarrierEffect", BarrierEffect}};
Effect::Effect(QString type, CCreature *caster, CCreature *victim)
    : className(type), bonus(nullptr), caster(caster), victim(victim) {
  if (effects.find(type) == effects.end()) {
    qFatal("Unknown historical effect callback");
  }
  timeLeft = timeTotal = effectConfiguration(type)["duration"].toInt();
}
int Effect::getTimeLeft() { return timeLeft; }
int Effect::getTimeTotal() { return timeTotal; }
CCreature *Effect::getCaster() { return caster; }
CCreature *Effect::getVictim() { return victim; }
Stats *Effect::getBonus() { return bonus; }
void Effect::setBonus(Stats *value) { bonus = value; }
bool Effect::apply(CCreature *creature) {
  if (timeLeft <= 0) {
    return false;
  }
  if (bonus && timeLeft == timeTotal) {
    creature->getStats()->addBonus(*bonus);
  }
  --timeLeft;
  if (!timeLeft) {
    if (bonus) {
      creature->getStats()->removeBonus(*bonus);
    }
    return false;
  }
  return effects.at(className)(this, creature);
}
QJsonObject Effect::saveToJson() {
  QJsonObject saved;
  saved["className"] = className;
  saved["timeLeft"] = timeLeft;
  saved["timeTotal"] = timeTotal;
  return saved;
}

bool StunEffect(Effect *, CCreature *) { return true; }
bool EndlessPainEffect(Effect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getDmg() * 15 / 100);
  return true;
}
bool AbyssalShadowsEffect(Effect *effect, CCreature *creature) {
  Damage damage;
  int amount = effect->getCaster()->getDmg();
  damage.setShadow(effect->getTimeLeft() > 1 ? amount * 45 / 100 : amount);
  creature->hurt(damage);
  return false;
}
bool ArmorOfEndlessWinterEffect(Effect *, CCreature *creature) {
  creature->healProc(20);
  return false;
}
bool MutilationEffect(Effect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getStats()->getAgility() / 4);
  return false;
}
bool LethalPoisonEffect(Effect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getDmg() * 4 / 6);
  return false;
}
bool ChloroformEffect(Effect *, CCreature *creature) {
  return creature->getHpRatio() > 25;
}
bool BloodlashEffect(Effect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getDmg() * 0.75);
  return false;
}
bool BarrierEffect(Effect *, CCreature *) { return false; }

void CInteraction::loadFromJson(QString name) {
  typeName = name;
  QJsonObject config =
      CConfigurationProvider::getConfig("config/objects/interactions.json")
          .toObject()[name]
          .toObject();
  manaCost = config["manaCost"].toInt();
  effect = config["effect"].toString();
  tooltip = config["tooltip"].toString(name);
  QString animation = config["anim"].toString();
  if (!animation.isEmpty())
    setAnimation(animation);
  statsView.setText(QString::number(manaCost));
}
