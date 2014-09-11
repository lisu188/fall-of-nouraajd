#include "CConfigurationProvider.h"
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

CItem::CItem(const CItem &item) : CItem() { this->loadFromJson(item.typeName); }

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

void CItem::onUse(CCreature *creature) {
  CItemSlot *parent = (CItemSlot *)this->parentItem();
  if (!parent) {
    qDebug() << "Parentless item dropped";
    return;
  }
  int slot = parent->getNumber();
  creature->setItem(slot, this);
}

void CItem::mousePressEvent(QGraphicsSceneMouseEvent *event) {
  if (singleUse && this->getMap()->getScene()->getPlayer()) {
    this->getMap()->getScene()->getPlayer()->removeFromInventory(this);
    onUse(this->getMap()->getScene()->getPlayer());
    delete this;
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

CArmor::CArmor(const CArmor &armor) {}

CInteraction *CArmor::getInteraction() { return interaction; }

CBelt::CBelt() {}

CBelt::CBelt(const CBelt &belt) {}

CBoots::CBoots() {}

CBoots::CBoots(const CBoots &boots) {}

CGloves::CGloves() {}

CGloves::CGloves(const CGloves &gloves) {}

CHelmet::CHelmet() {}

CHelmet::CHelmet(const CHelmet &helmet) {}

CSmallWeapon::CSmallWeapon() {}

CSmallWeapon::CSmallWeapon(const CSmallWeapon &weapon) {}

CWeapon::CWeapon() : CItem() {}

CWeapon::CWeapon(const CWeapon &weapon) {}

CInteraction *CWeapon::getInteraction() { return interaction; }

void CItem::loadFromJson(QString name) {
  setTypeName(name);
  QJsonObject config = itemConfiguration(name);
  QJsonObject properties =
      config.contains("properties") ? config["properties"].toObject() : config;
  QJsonObject stats = properties["bonus"].toObject();
  for (auto it = stats.begin(); it != stats.end(); ++it) {
    bonus.setProperty(it.key(), it.value().toVariant());
  }
  setAnimation(properties["animation"].toString());
  power = properties["power"].toInt(1);
  singleUse = properties["singleUse"].toBool(false);
  tooltip = properties["tooltip"].toString(name);
  slot = properties["slot"].toInt();
  QString action = properties["interaction"].toString();
  interaction =
      map && !action.isEmpty()
          ? map->getObjectHandler()->createMapObject<CInteraction *>(action)
          : nullptr;
}

Stats CItem::getBonus() { return bonus; }
void CItem::setBonus(Stats value) { bonus = value; }
CArmor::CArmor(QString name) { loadFromJson(name); }

CPotion::CPotion() : effect(nullptr) {}
CPotion::CPotion(const CPotion &potion) : CPotion() {
  loadFromJson(potion.typeName);
}
void CPotion::onUse(CCreature *creature) {
  if (!effect) {
    if (typeName.contains("LifePotion"))
      effect = &LifeEffect;
    else if (typeName.contains("ManaPotion"))
      effect = &ManaEffect;
  }
  if (!effect)
    qFatal("Unknown potion effect");
  effect(creature, power);
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
void CScroll::onUse(CCreature *) {
  CGameView *view = getMap()->getScene()->getView();
  CScrollPanel *panel =
      dynamic_cast<CScrollPanel *>(view->getPanel("CScrollPanel"));
  if (!panel)
    qFatal("Missing registered scroll text panel");
  panel->setText(text);
  view->showPanel("CScrollPanel");
}
