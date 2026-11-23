#include "CCreature.h"
#include "CGamePanel.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CMapObject.h"
#include "CPlayerView.h"
#include <QPainter>

AGamePanel::AGamePanel() {
  setVisible(false);
  setZValue(10);
}
AGamePanel::AGamePanel(const AGamePanel &) : AGamePanel() {}
void AGamePanel::setUpPanel(CGameView *view) {
  if (scene() != view->getScene())
    view->getScene()->addItem(this);
}
void AGamePanel::showPanel(CGameView *view) {
  setUpPanel(view);
  setPos(view->mapToScene(20, 100));
  setVisible(!isVisible());
  update();
}
QRectF AGamePanel::boundingRect() const { return childrenBoundingRect(); }
void AGamePanel::paint(QPainter *, const QStyleOptionGraphicsItem *,
                       QWidget *) {}

CCharPanel::CCharPanel()
    : playerInventoryView(nullptr), playerEquippedView(nullptr) {}
CCharPanel::CCharPanel(const CCharPanel &) : CCharPanel() {}
QRectF CCharPanel::boundingRect() const { return QRectF(0, 0, 400, 250); }
void CCharPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *,
                       QWidget *) {
  painter->fillRect(boundingRect(), QColor(30, 30, 30, 230));
}
void CCharPanel::setUpPanel(CGameView *view) {
  AGamePanel::setUpPanel(view);
  if (playerInventoryView)
    return;
  CPlayer *player = view->getScene()->getPlayer();
  playerInventoryView = new CPlayerListView(
      (std::set<CMapObject *, Comparer<CMapObject>> *)player->getInventory());
  playerInventoryView->setParentItem(this);
  playerEquippedView = new CPlayerEquippedView(player->getEquipped());
  playerEquippedView->setParentItem(this);
  playerEquippedView->setPos(200, 0);
  connect(player, SIGNAL(inventoryChanged()), playerInventoryView,
          SLOT(update()));
  connect(player, SIGNAL(equippedChanged()), playerEquippedView,
          SLOT(update()));
}
void CCharPanel::showPanel(CGameView *view) { AGamePanel::showPanel(view); }

CCreature *CFightPanel::selected = nullptr;
CFightPanel::CFightPanel() : playerSkillsView(nullptr) {}
CFightPanel::CFightPanel(const CFightPanel &) : CFightPanel() {}
QRectF CFightPanel::boundingRect() const { return QRectF(0, 0, 200, 150); }
void CFightPanel::setUpPanel(CGameView *view) {
  AGamePanel::setUpPanel(view);
  if (playerSkillsView)
    return;
  CPlayer *player = view->getScene()->getPlayer();
  playerSkillsView = new CPlayerListView(
      (std::set<CMapObject *, Comparer<CMapObject>> *)player->getActions());
  playerSkillsView->setXY(4, 1);
  playerSkillsView->setParentItem(this);
  playerSkillsView->setPos(0, 50);
  connect(player, SIGNAL(skillsChanged()), playerSkillsView, SLOT(update()));
}
void CFightPanel::showPanel(CGameView *view) {
  setUpPanel(view);
  setPos(view->mapToScene(20, 100));
  if (!selected && !view->getScene()->getPlayer()->getFightList()->empty())
    selected = view->getScene()->getPlayer()->getFightList()->front();
  setVisible(true);
  update();
}
void CFightPanel::update() { QGraphicsObject::update(); }
void CFightPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *,
                        QWidget *) {
  painter->fillRect(boundingRect(), QColor(30, 30, 30, 230));
  if (!selected)
    return;
  painter->setPen(Qt::white);
  painter->drawText(QRectF(0, 0, 200, 50), Qt::AlignCenter,
                    QString("%1: %2/%3")
                        .arg(selected->getTypeName())
                        .arg(selected->getHp())
                        .arg(selected->getHpMax()));
}
