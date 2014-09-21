#include "CConfigurationProvider.h"
#include "CGuiHandler.h"
#include "CCreature.h"
#include "CGamePanel.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CInteraction.h"
#include "CItem.h"
#include "CObjectHandler.h"
#include "CPlayerView.h"
#include "CTypeHandler.h"
#include <QDebug>
#include <QDirIterator>
#include <QFileInfo>
#include <QGraphicsSceneMouseEvent>

namespace {
QJsonObject itemConfiguration(QString name) {
  QDirIterator files("config/objects", QStringList() << "*.json", QDir::Files,
                     QDirIterator::Subdirectories);
  while (files.hasNext()) {
    QJsonObject contents =
        CConfigurationProvider::getConfig(files.next()).toObject();
    if (contents.contains(name)) {
      return contents[name].toObject();
    }
  }
  return QJsonObject();
}
} // namespace
CItem::CItem() : interaction(nullptr) { setZValue(2); }

CItem::CItem(const CItem &item) : CItem() {
  typeName = item.typeName;
  tooltip = item.tooltip;
  bonus = item.bonus;
  power = item.power;
  singleUse = item.singleUse;
  interaction = item.interaction;
  slot = item.slot;
  setAnimation(item.property("animation").toString());
}

void CItem::onEnter() {
  this->getMap()->removeObject(this);
  this->getMap()->getScene()->getPlayer()->addItem(this);
}

void CItem::onMove() {}

bool CItem::isSingleUse() { return singleUse; }

void CItem::setSingleUse(bool singleUse) { this->singleUse = singleUse; }

void CItem::onEquip(CCreature *creature) {
  creature->getStats()->addBonus(bonus);
  qDebug() << creature->typeName << "equipped" << typeName << "\n";
}

void CItem::onUnequip(CCreature *creature) {
  creature->getStats()->removeBonus(bonus);
  qDebug() << creature->typeName << "unequipped" << typeName << "\n";
}

bool CItem::onUse(CCreature *creature) {
  CItemSlot *parent = (CItemSlot *)this->parentItem();
  if (!parent) {
    qDebug() << "Parentless item dropped";
    return false;
  }
  int slot = parent->getNumber();
  creature->setItem(slot, this);
  return false;
}

void CItem::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  if (singleUse && this->getMap()->getScene()->getPlayer()) {
    if (onUse(this->getMap()->getScene()->getPlayer())) {
      this->getMap()->getScene()->getPlayer()->removeFromInventory(this);
      delete this;
    }
    return;
  }
  CMapObject::mousePressEvent(event);
  if (event->isAccepted()) {
    return;
  }
  if (this->getMap()->getScene()->getPlayer() &&
      !this->getMap()->getScene()->getPlayer()->hasItem(this)) {
    return;
  }
  QGraphicsObject *parent = this->parentObject();
  if (parent) {
    parent->setAcceptDrops(false);
  }
  CAnimatedObject::mousePressEvent(event);
  if (parent) {
    parent->setAcceptDrops(true);
  }
}

int CItem::getPower() const { return power; }

void CItem::setPower(int value) { power = value; }

CArmor::CArmor() {}

CArmor::CArmor(const CArmor &armor) : CItem(armor) {}

CInteraction *CArmor::getInteraction() { return interaction; }

CBelt::CBelt() {}

CBelt::CBelt(const CBelt &belt) : CItem(belt) {}

CBoots::CBoots() {}

CBoots::CBoots(const CBoots &boots) : CItem(boots) {}

CGloves::CGloves() {}

CGloves::CGloves(const CGloves &gloves) : CItem(gloves) {}

CHelmet::CHelmet() {}

CHelmet::CHelmet(const CHelmet &helmet) : CItem(helmet) {}

CSmallWeapon::CSmallWeapon() {}

CSmallWeapon::CSmallWeapon(const CSmallWeapon &weapon) : CWeapon(weapon) {}

CWeapon::CWeapon() : CItem() {}

CWeapon::CWeapon(const CWeapon &weapon) : CItem(weapon) {}

CInteraction *CWeapon::getInteraction() { return interaction; }

Stats CItem::getBonus() { return bonus; }
void CItem::setBonus(Stats value) { bonus = value; }
CArmor::CArmor(QString name) {
  setTypeName(name);
  QJsonObject config = itemConfiguration(name);
  QJsonObject properties =
      config.contains("properties") ? config["properties"].toObject() : config;
  QJsonObject fields = properties["bonus"].toObject();
  for (auto it = fields.begin(); it != fields.end(); ++it)
    bonus.setProperty(it.key(), it.value().toVariant());
  setAnimation(properties["animation"].toString());
  power = properties["power"].toInt();
  singleUse = properties["singleUse"].toBool();
  tooltip = properties["tooltip"].toString(name);
}

CPotion::CPotion() : effect(nullptr) {}
CPotion::CPotion(const CPotion &potion)
    : CItem(potion), effect(potion.effect) {}
bool CPotion::onUse(CCreature *creature) {
  if (!effect) {
    if (typeName.contains("LifePotion"))
      effect = &LifeEffect;
    else if (typeName.contains("ManaPotion"))
      effect = &ManaEffect;
  }
  if (!effect)
    qFatal("Unknown potion effect");
  effect(creature, power);
  return true;
}

void LifeEffect(CCreature *creature, int power) {
  creature->healProc(power * 20);
}
void ManaEffect(CCreature *creature, int power) {
  creature->addManaProc(power * 20);
}

QString CItem::getInteractionName() {
  return interaction ? interaction->getTypeName() : QString();
}
void CItem::setInteractionName(QString name) {
  if (getInteractionName() == name)
    return;
  if (name.isEmpty()) {
    interaction = nullptr;
    return;
  }
  if (!map)
    qFatal("Cannot resolve item interaction without its map");
  interaction = map->getObjectHandler()->createMapObject<CInteraction *>(name);
  if (!interaction)
    qFatal("Configured item interaction is not a CInteraction");
}

CScroll::CScroll() {}
CScroll::CScroll(const CScroll &scroll) : CItem(scroll), text(scroll.text) {}
QString CScroll::getText() const { return text; }
void CScroll::setText(const QString &value) { text = value; }
bool CScroll::onUse(CCreature *) {
  CGameView *view = getMap()->getScene()->getView();
  CTextPanel *panel =
      dynamic_cast<CTextPanel *>(view->getScene()->getMap()->getGuiHandler()->getPanel("CTextPanel"));
  if (!panel)
    qFatal("Missing registered scroll text panel");
  panel->setText(text);
  panel->showPanel();
  return true;
}
