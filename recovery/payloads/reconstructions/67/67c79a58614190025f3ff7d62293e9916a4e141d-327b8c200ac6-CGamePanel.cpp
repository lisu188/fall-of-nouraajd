#include "CCreature.h"
#include "CGamePanel.h"
#include "CGameScene.h"
#include "CGameView.h"
#include "CMap.h"
#include "CMapObject.h"
#include "CPlayerView.h"
#include <QMouseEvent>
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
    : playerInventoryView(nullptr), playerEquippedView(nullptr),
      backpack(nullptr) {}
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
  if (!backpack) {
    backpack = new BackPackObject(view);
    backpack->show();
  }
  CMap *map = view->getScene()->findChild<CMap *>(QString(),
                                                  Qt::FindDirectChildrenOnly);
  CPlayer *player = map ? map->getPlayer() : nullptr;
  if (!player)
    return;
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
void CCharPanel::showPanel(CGameView *view) {
  AGamePanel::showPanel(view);
  if (backpack)
    backpack->move(view->width() - backpack->width(), 0);
}

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

BackPackObject::BackPackObject(CGameView *view)
    : QWidget(view), pixmap("images/backpack.png"), view(view) {
  setFixedSize(pixmap.size());
  setAttribute(Qt::WA_TranslucentBackground);
  move(view->width() - width(), 0);
}
void BackPackObject::mousePressEvent(QMouseEvent *event) {
  if (event->button() == Qt::LeftButton) {
    view->showPanel("CCharPanel");
    event->accept();
  } else {
    QWidget::mousePressEvent(event);
  }
}
void BackPackObject::paintEvent(QPaintEvent *) {
  QPainter painter(this);
  painter.drawPixmap(0, 0, pixmap);
}

CScrollPanel::CScrollPanel() { setZValue(7); }
CScrollPanel::CScrollPanel(const CScrollPanel &panel) : CScrollPanel() {
  text = panel.text;
}
QRectF CScrollPanel::boundingRect() const { return QRectF(0, 0, 400, 300); }
void CScrollPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *,
                         QWidget *) {
  painter->fillRect(boundingRect(), QColor("BLACK"));
  painter->setPen(QColor("WHITE"));
  painter->drawText(QRectF(0, painter->font().pointSize(), 400, 300),
                    Qt::AlignLeft | Qt::TextWordWrap | Qt::AlignJustify, text);
}
void CScrollPanel::showPanel(CGameView *view) {
  setUpPanel(view);
  setPos(view->mapToScene(view->width() / 2 - boundingRect().width() / 2,
                          view->height() / 2 - boundingRect().height() / 2));
  setVisible(true);
  update();
}
void CScrollPanel::setUpPanel(CGameView *view) { AGamePanel::setUpPanel(view); }
QString CScrollPanel::getText() const { return text; }
void CScrollPanel::setText(const QString &value) {
  text = value;
  update();
}
