#include "CGamePanel.h"
#include "CGameView.h"
#include "CGameScene.h"
#include <src/CInteraction.h>
#include <src/CItem.h>
#include <src/CCreature.h>
#include <src/CPlayerView.h>
#include <src/CPlayerView.h>
#include <QPainter>
#include <map>
#include <set>

namespace {
// CPlayer containers mirrored as the CMapObject sets CPlayerListView displays.
struct PanelLists {
    std::set<CMapObject *, Comparer<CMapObject>> inventory;
    std::set<CMapObject *, Comparer<CMapObject>> skills;
};
std::map<const AGamePanel *, PanelLists> panelLists;

void copyInventory(CPlayer *player, std::set<CMapObject *, Comparer<CMapObject>> &list) {
    list.clear();
    for (CItem *item : *player->getInventory())
        list.insert(item);
}

void copySkills(CPlayer *player, std::set<CMapObject *, Comparer<CMapObject>> &list) {
    list.clear();
    for (CInteraction *action : *player->getActions())
        list.insert(action);
}

void refresh(QObject *view) {
    if (view)
        QMetaObject::invokeMethod(view, "update", Qt::DirectConnection);
}
} // namespace

CCharPanel::CCharPanel() : playerInventoryView(0), playerEquippedView(0) {
    setZValue(6);
    setVisible(false);
}

CCharPanel::CCharPanel(const CCharPanel &) : CCharPanel() {}

QRectF CCharPanel::boundingRect() const { return QRectF(0, 0, 400, 300); }

void CCharPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *) {
    painter->fillRect(boundingRect(), QColor("BLACK"));
}

void CCharPanel::setUpPanel(CGameView *view) {
    CPlayer *player = view->getScene()->getPlayer();
    PanelLists &lists = panelLists[this];
    copyInventory(player, lists.inventory);
    playerInventoryView = new CPlayerListView(&lists.inventory);
    playerEquippedView = new CPlayerEquippedView(player->getEquipped());
    playerInventoryView->setParentItem(this);
    playerEquippedView->setParentItem(this);
    playerInventoryView->setPos(0, 0);
    playerEquippedView->setPos(boundingRect().width() - playerEquippedView->boundingRect().width(), 0);
}

void CCharPanel::showPanel(CGameView *view) {
    if (!playerInventoryView || !playerEquippedView)
        return;
    if (isVisible()) {
        setVisible(false);
        return;
    }
    copyInventory(view->getScene()->getPlayer(), panelLists[this].inventory);
    refresh(playerInventoryView);
    refresh(playerEquippedView);
    setVisible(true);
    setPos(view->mapToScene(view->width() / 2 - boundingRect().width() / 2,
                            view->height() / 2 - boundingRect().height() / 2));
    QGraphicsItem::update();
}

CCreature *CFightPanel::selected = 0;

CFightPanel::CFightPanel() : playerSkillsView(0) {
    setZValue(5);
    setVisible(false);
}

CFightPanel::CFightPanel(const CFightPanel &) : CFightPanel() {}

QRectF CFightPanel::boundingRect() const { return QRectF(0, 0, 400, 300); }

void CFightPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *) {
    painter->fillRect(boundingRect(), QColor("BLACK"));
}

void CFightPanel::setUpPanel(CGameView *view) {
    CPlayer *player = view->getScene()->getPlayer();
    PanelLists &lists = panelLists[this];
    copySkills(player, lists.skills);
    playerSkillsView = new CPlayerListView(&lists.skills);
    playerSkillsView->setParentItem(this);
    playerSkillsView->setPos(0, boundingRect().height() - playerSkillsView->boundingRect().height());
}

void CFightPanel::update() {
    CGameScene *gameScene = dynamic_cast<CGameScene *>(this->scene());
    if (gameScene && gameScene->getPlayer()) {
        copySkills(gameScene->getPlayer(), panelLists[this].skills);
        refresh(playerSkillsView);
    }
    QGraphicsItem::update();
}

void CFightPanel::showPanel(CGameView *view) {
    std::list<CCreature *> *fightList = view->getScene()->getPlayer()->getFightList();
    if (!fightList->empty())
        selected = fightList->front();
    setVisible(true);
    setPos(view->mapToScene(view->width() / 2 - boundingRect().width() / 2,
                            view->height() / 2 - boundingRect().height() / 2));
    update();
}
