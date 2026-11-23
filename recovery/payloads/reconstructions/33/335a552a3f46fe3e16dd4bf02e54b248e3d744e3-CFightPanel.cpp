#include "CCreature.h"
#include "CGuiHandler.h"
#include "CGamePanel.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CMap.h"
#include "CMapObject.h"
#include "CPlayerView.h"
#include <QGraphicsSceneMouseEvent>
#include <QMouseEvent>
#include <QPainter>

AGamePanel::AGamePanel() {
  setVisible(false);
  setZValue(10);
}
AGamePanel::AGamePanel(const AGamePanel &) : AGamePanel() {}
void AGamePanel::setUpPanel(CGameView *view) {
  this->view = view;
  if (scene() != view->getScene())
    view->getScene()->addItem(this);
}
void AGamePanel::hidePanel() { setVisible(false); }
bool AGamePanel::isShown() { return isVisible(); }
QString AGamePanel::getPanelName() { return metaObject()->className(); }
void AGamePanel::update() { QGraphicsItem::update(); }
void AGamePanel::showPanel() {
  if (!view) return;
  setPos(view->mapToScene(20, 100));
  setVisible(!isVisible());
  update();
}
QRectF AGamePanel::boundingRect() const { return childrenBoundingRect(); }
void AGamePanel::paint(QPainter *, const QStyleOptionGraphicsItem *,
                       QWidget *) {}

CFightPanel::CFightPanel() : playerSkillsView(nullptr) {}
CFightPanel::CFightPanel(const CFightPanel &) : CFightPanel() {}
QRectF CFightPanel::boundingRect() const { return QRectF(0, 0, 200, 150); }
void CFightPanel::setUpPanel(CGameView *view) {
  AGamePanel::setUpPanel(view);
  if (playerSkillsView)
    return;
  CPlayer *player = view->getScene()->getPlayer();
  playerSkillsView = new CPlayerIteractionView(view);
  playerSkillsView->setXY(4, 1);
  playerSkillsView->setParentItem(this);
  playerSkillsView->setPos(0, 50);
}
void CFightPanel::showPanel() {
  if (!view) return;
  setPos(view->mapToScene(20, 100));
  setVisible(true);
  update();
}
void CFightPanel::update() {
  if (playerSkillsView) playerSkillsView->update();
  AGamePanel::update();
}
void CFightPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *,
                        QWidget *) {
  painter->fillRect(boundingRect(), QColor(30, 30, 30, 230));
  auto *player = view->getScene()->getPlayer();
  auto *selected = player && !player->getFightList()->empty() ? player->getFightList()->front() : nullptr;
  if (!selected)
    return;
  painter->setPen(Qt::white);
  painter->drawText(QRectF(0, 0, 200, 50), Qt::AlignCenter,
                    QString("%1: %2/%3")
                        .arg(selected->getObjectType())
                        .arg(selected->getHp())
                        .arg(selected->getHpMax()));
}

