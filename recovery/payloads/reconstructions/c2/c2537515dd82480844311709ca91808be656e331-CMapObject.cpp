#include <src/lootprovider.h>
#include <locale>
#include <QGraphicsSceneHoverEvent>
#include "CMap.h"


#include "tile.h"

#include <src/CBuilding.h>
#include <src/CPathFinder.h>
#include <src/CConfigurationProvider.h>
#include <src/CCreature.h>
#include <src/CInteraction.h>
#include <src/item.h>
#include <src/gamescene.h>
#include <src/gameview.h>
#include <src/scriptmanager.h>

#include <QApplication>
#include <QDesktopWidget>
#include <QGraphicsSceneMouseEvent>
#include <QMetaType>
#include <QMetaProperty>
#include <QWidget>
#include <algorithm>
#include <cstdlib>
#include <vector>
#include <QDebug>
#include <lib/tmx/TmxLayer.h>
#include <lib/tmx/TmxTileset.h>
#include <lib/tmx/TmxTile.h>
#include <lib/tmx/TmxObject.h>
#include <lib/tmx/TmxObjectGroup.h>

const int animation_step_ms = 100;
class ReconstructedPlayerAnimation : public QGraphicsItemAnimation {
public:
    explicit ReconstructedPlayerAnimation(QObject *parent) : QGraphicsItemAnimation(parent) {}
protected:
    void afterAnimationStep(qreal step) override;
};

void ReconstructedPlayerAnimation::afterAnimationStep(qreal) {
    QGraphicsItem *animated = item();
    CGameScene *scene = animated ? dynamic_cast<CGameScene *>(animated->scene()) : NULL;
    if (scene && scene->getView()) scene->getView()->centerOn(animated);
}
CMapObject::CMapObject() : CMapObject(0, 0, 0, 0) {}

CMapObject::CMapObject(int x, int y, int z, int v) {
  posx = x;
  posy = y;
  posz = z;
  setZValue(v);
  setAcceptHoverEvents(true);
  statsView.setParentItem(this);
  statsView.setVisible(true);
  statsView.setText(" ");
  statsView.setPos(-this->mapToParent(0, 0).x(), -statsView.boundingRect().height());
}

void CMapObject::moveTo(int x, int y, int z, bool silent) {
    QPointF from = QGraphicsItem::pos();
    posx = x; posy = y; posz = z;
    QPointF to(x * CMap::getTileSize(), y * CMap::getTileSize());
    if (!silent && map && map->getScene()->getView() && from != to) {
        QGraphicsItemAnimation *animation = inherits("Player")
            ? static_cast<QGraphicsItemAnimation *>(new ReconstructedPlayerAnimation(this))
            : new QGraphicsItemAnimation(this);
        QTimeLine *timeline = new QTimeLine(animation_step_ms, animation);
        animation->setItem(this);
        animation->setTimeLine(timeline);
        animation->setPosAt(0, from); animation->setPosAt(1, to);
        connect(timeline, &QTimeLine::finished, animation, &QObject::deleteLater);
        timeline->start();
    } else { setPos(to); }
    if (map) QGraphicsItem::setVisible(posz == map->getCurrentMap());
    if (!silent) {
        Player *player = map ? map->getScene()->getPlayer() : NULL;
        if (player && player != this && player->getPosX() == posx && player->getPosY() == posy && player->getPosZ() == posz)
            player->addEntered(this);
    }
}

int CMapObject::getPosX() const { return posx; }

int CMapObject::getPosY() const { return posy; }

int CMapObject::getPosZ() const { return posz; }

void CMapObject::removeFromGame() {
  if (map) {
    CMap *owner = map;
    map = 0;
    owner->removeObject(this);
  }
}

void CMapObject::move(int x, int y) {
  if (!map) {
    return;
  }

  int next_x = posx + x;
  int next_y = posy + y;
  int next_z = posz;
  std::string tile_name = map->getTile(next_x, next_y, next_z);
  if (tile_name.compare("") == 0) {
    return;
  }

  Tile *tile = Tile::getTile(tile_name, next_x, next_y, next_z);
  bool can_step = tile && tile->canStep();
  delete tile;
  if (!can_step) {
    return;
  }

  moveTo(next_x, next_y, next_z);
}

void CMapObject::setMap(CMap *map) {
  this->map = map;
  if (!map) {
    return;
  }
  if (scene() != map->getScene()) {
    map->getScene()->addItem(this);
  }
  setPos(posx * CMap::getTileSize(), posy * CMap::getTileSize());
  QGraphicsItem::setVisible(posz == map->getCurrentMap());
}

CMap *CMapObject::getMap() { return map; }

void CMapObject::setVisible(bool vis) { QGraphicsItem::setVisible(vis); }

void CMapObject::setAnimation(std::string path) {
  CAnimatedObject::setAnimation(path, CMap::getTileSize());
}
void CMapObject::loadFromProps(Tmx::PropertySet properties) {
    for (auto property : properties.GetList()) {
        int index = metaObject()->indexOfProperty(property.first.c_str());
        if (index < 0 || !metaObject()->property(index).isUser()) continue;
        QMetaProperty metadata = metaObject()->property(index);
        QVariant value(QString::fromStdString(property.second));
        if (!value.convert(metadata.type()) || !metadata.write(this, value))
            qWarning() << "Could not apply authored TMX property" << property.first.c_str();
    }
}
void CMapObject::onEnter() {}

void CMapObject::onMove() {}

void CMapObject::onCreate() {}

void CMapObject::onDestroy() {}
void CMapObject::setNumber(int i, int x) {
  this->QGraphicsItem::setVisible(true);
  int px = i % x * CMap::getTileSize();
  int py = i / x * CMap::getTileSize();
  this->QGraphicsItem::setPos(px, py);
}

bool CMapObject::compare(CMapObject *item) {
  int value = toLower(typeName).compare(toLower(item->typeName));
  if (value == 0) {
    return this < item;
  }
  return value < 0;
}

void CMapObject::hoverEnterEvent(QGraphicsSceneHoverEvent *event) {
  statsView.setVisible(true);
  statsView.setText(tooltip.c_str());
  statsView.setPos(0, 0 - statsView.boundingRect().height());
  event->setAccepted(true);
}

void CMapObject::hoverLeaveEvent(QGraphicsSceneHoverEvent *event) {
  statsView.setVisible(false);
  event->setAccepted(true);
}

#include "CMapObject.h"
#include "scriptmanager.h"

CEvent::CEvent() {}

CEvent::CEvent ( const CEvent & ) {}

void CEvent::onEnter() {
	if ( this->isEnabled() ) {
		map->getEngine()->executeScript ( script );
	}
}

void CEvent::onMove() {}

void CEvent::loadFromJson ( std::string name ) {}
QString CEvent::getScript() const { return script; }

void CEvent::setScript ( const QString &value ) { script = value; }

bool CEvent::isEnabled() { return enabled; }

void CEvent::setEnabled ( bool enabled ) { this->enabled = enabled; }

Coords CMapObject::getCoords() { return Coords(posx, posy, posz); }
void CMapObject::setCoords(Coords coords) { moveTo(coords.x, coords.y, coords.z); }
