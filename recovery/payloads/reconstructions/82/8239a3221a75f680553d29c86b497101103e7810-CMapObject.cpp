#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CMap.h"
#include "CMapObject.h"
#include "CTile.h"
#include <QGraphicsSceneHoverEvent>

CMapObject::CMapObject() : posx(0), posy(0), posz(0) {
  setAcceptHoverEvents(true);
}

int CMapObject::getPosX() const { return posx; }
int CMapObject::getPosY() const { return posy; }
int CMapObject::getPosZ() const { return posz; }

namespace {
bool mapTileCanStep(CMap *map, int x, int y, int z) {
  return CConfigurationProvider::getConfig("config/objects/tiles.json")
      .toObject()[map->getTile(x, y, z)]
      .toObject()["canStep"]
      .toBool();
}
} // namespace

void CMapObject::move(int x, int y) {
  if (map && !mapTileCanStep(map, posx + x, posy + y, posz)) {
    return;
  }
  moveTo(posx + x, posy + y, posz, true);
}
void CMapObject::moveTo(int x, int y, int z, bool silent) {
  if (map && !silent && !mapTileCanStep(map, x, y, z)) {
    return;
  }
  posx = x;
  posy = y;
  posz = z;
  setPos(x * 50, y * 50);
}
void CMapObject::removeFromGame() {
  if (map) {
    map->removeObject(this);
  }
}
void CMapObject::onEnter() {}
void CMapObject::onMove() {}
void CMapObject::onCreate() {}
void CMapObject::onDestroy() {}
void CMapObject::loadFromJson(QString name) { typeName = name; }
void CMapObject::loadFromProps(Tmx::PropertySet properties) {
  for (auto &entry : properties.GetList()) {
    QString value = QString::fromStdString(entry.second);
    bool integer = false;
    int number = value.toInt(&integer);
    QVariant converted = integer            ? QVariant(number)
                         : value == "true"  ? QVariant(true)
                         : value == "false" ? QVariant(false)
                                            : QVariant(value);
    setProperty(QString::fromStdString(entry.first), converted);
  }
}
void CMapObject::setMap(CMap *value) {
  if (!value) {
    return;
  }
  map = value;
  QObject::setParent(nullptr);
  QWidget::setParent(map->getScene()->getView());
  moveTo(posx, posy, posz, true);
  if (scene() != map->getScene()) {
    map->getScene()->addItem(this);
  }
}
void CMapObject::setAnimation(QString path) { CAnimatedObject::setAnimation(path, CMap::getTileSize()); }
CMap *CMapObject::getMap() { return map; }
void CMapObject::setVisible(bool value) {
  QGraphicsPixmapItem::setVisible(value);
}
Coords CMapObject::getCoords() { return Coords(posx, posy, posz); }
void CMapObject::setCoords(Coords coords) {
  moveTo(coords.x, coords.y, coords.z);
}
void CMapObject::setNumber(int index, int width) {
  QGraphicsItem::setVisible(true);
  QGraphicsItem::setPos((index % width) * 50, (index / width) * 50);
}
bool CMapObject::compare(CMapObject *item) {
  int order = typeName.toLower().compare(item->typeName.toLower());
  return order ? order < 0 : this < item;
}
void CMapObject::hoverEnterEvent(QGraphicsSceneHoverEvent *event) {
  event->accept();
}
void CMapObject::hoverLeaveEvent(QGraphicsSceneHoverEvent *event) {
  event->accept();
}

CEvent::CEvent() {}
CEvent::CEvent(const CEvent &event) : CEvent() {
  enabled = event.enabled;
  script = event.script;
}
void CEvent::onEnter() {
  if (enabled) {
    map->getEngine()->executeScript(script);
  }
}
void CEvent::onMove() {}
void CEvent::loadFromJson(QString name) { CMapObject::loadFromJson(name); }
QString CEvent::getScript() const { return script; }
void CEvent::setScript(const QString &value) { script = value; }
bool CEvent::isEnabled() { return enabled; }
void CEvent::setEnabled(bool value) { enabled = value; }
