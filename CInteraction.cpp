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
  qDebug() << first->getTypeName() << "used" << getTypeName() << "against"
           << second->getTypeName();
  performAction(first, second);
  if (!effect.isEmpty()) {
    CCreature *victim =
        effectConfiguration(effect)["buff"].toBool() ? first : second;
    CEffect *active = new CEffect(effect, first, victim);
    if (configureEffect(active)) {
      victim->addEffect(active);
    } else {
      delete active;
    }
  }
}
void CInteraction::performAction(CCreature *first, CCreature *second) {
  PY_UNSAFE(boost::python::object function =
                CScriptEngine::getInstance()
                    ->getObject("game")
                    .attr("interaction")
                    .attr(typeName.toStdString().c_str());
            function(boost::python::ptr(first), boost::python::ptr(second));)
}
bool CInteraction::configureEffect(CEffect *) { return true; }
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
int CInteraction::getManaCost() const { return manaCost; }
void CInteraction::setManaCost(int value) {
  manaCost = value;
  statsView.setText(QString::number(value));
}
QString CInteraction::getEffect() const { return effect; }
void CInteraction::setEffect(const QString &value) { effect = value; }

std::map<QString, std::function<bool(CEffect *, CCreature *)>> CEffect::effects =
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
CEffect::CEffect() : timeLeft(0), timeTotal(0), caster(nullptr), victim(nullptr) {}
CEffect::CEffect(const CEffect &effect) : CEffect() {
  className = effect.className;
  timeLeft = effect.timeLeft;
  timeTotal = effect.timeTotal;
  caster = effect.caster;
  victim = effect.victim;
}

CEffect::CEffect(QString type, CCreature *caster, CCreature *victim)
    : CEffect() {
  className = type;
  this->caster = caster;
  this->victim = victim;
  if (effects.find(type) == effects.end()) {
    qFatal("Unknown historical effect callback");
  }
  timeLeft = timeTotal = effectConfiguration(type)["duration"].toInt();
}
int CEffect::getTimeLeft() { return timeLeft; }
int CEffect::getTimeTotal() { return timeTotal; }
CCreature *CEffect::getCaster() { return caster; }
CCreature *CEffect::getVictim() { return victim; }
Stats *CEffect::getBonus() { return bonus; }
void CEffect::setBonus(Stats *value) { bonus = value; }
bool CEffect::apply(CCreature *creature) {
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

bool StunEffect(CEffect *, CCreature *) { return true; }
bool EndlessPainEffect(CEffect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getDmg() * 15 / 100);
  return true;
}
bool AbyssalShadowsEffect(CEffect *effect, CCreature *creature) {
  Damage damage;
  int amount = effect->getCaster()->getDmg();
  damage.setShadow(effect->getTimeLeft() > 1 ? amount * 45 / 100 : amount);
  creature->hurt(damage);
  return false;
}
bool ArmorOfEndlessWinterEffect(CEffect *, CCreature *creature) {
  creature->healProc(20);
  return false;
}
bool MutilationEffect(CEffect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getStats()->getAgility() / 4);
  return false;
}
bool LethalPoisonEffect(CEffect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getDmg() * 4 / 6);
  return false;
}
bool ChloroformEffect(CEffect *, CCreature *creature) {
  return creature->getHpRatio() > 25;
}
bool BloodlashEffect(CEffect *effect, CCreature *creature) {
  creature->hurt(effect->getCaster()->getDmg() * 0.75);
  return false;
}
bool BarrierEffect(CEffect *, CCreature *) { return false; }
