#include "gamepanel.h"
#include "gameview.h"
#include "gamescene.h"
#include <src/interaction.h>
#include <src/item.h>
#include <src/player.h>
#include <src/playerequippedview.h>
#include <src/playerlistview.h>
#include <QPainter>
#include <map>
#include <set>

namespace {
// Player containers mirrored as the MapObject sets PlayerListView displays.
struct PanelLists {
    std::set<MapObject *, Comparer> inventory;
    std::set<MapObject *, Comparer> skills;
};
std::map<const GamePanel *, PanelLists> panelLists;

void copyInventory(Player *player, std::set<MapObject *, Comparer> &list) {
    list.clear();
    for (Item *item : *player->getInventory())
        list.insert(item);
}

void copySkills(Player *player, std::set<MapObject *, Comparer> &list) {
    list.clear();
    for (Interaction *action : *player->getActions())
        list.insert(action);
}

void refresh(QObject *view) {
    if (view)
        QMetaObject::invokeMethod(view, "update", Qt::DirectConnection);
}
} // namespace

GamePanel::GamePanel() {}

GamePanel::GamePanel(const GamePanel &) {}

void GamePanel::showPanel(GameView *) {}

void GamePanel::setUpPanel(GameView *) {}

QRectF GamePanel::boundingRect() const { return QRectF(0, 0, 400, 300); }

void GamePanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *) {
    painter->fillRect(boundingRect(), QColor("BLACK"));
}

CharPanel::CharPanel() : playerInventoryView(0), playerEquippedView(0) {
    setZValue(6);
    setVisible(false);
}

CharPanel::CharPanel(const CharPanel &) : CharPanel() {}

QRectF CharPanel::boundingRect() const { return QRectF(0, 0, 400, 300); }

void CharPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *) {
    painter->fillRect(boundingRect(), QColor("BLACK"));
}

void CharPanel::setUpPanel(GameView *view) {
    Player *player = view->getScene()->getPlayer();
    PanelLists &lists = panelLists[this];
    copyInventory(player, lists.inventory);
    playerInventoryView = new PlayerListView(&lists.inventory);
    playerEquippedView = new PlayerEquippedView(player->getEquipped());
    playerInventoryView->setParentItem(this);
    playerEquippedView->setParentItem(this);
    playerInventoryView->setPos(0, 0);
    playerEquippedView->setPos(boundingRect().width() - playerEquippedView->boundingRect().width(), 0);
}

void CharPanel::showPanel(GameView *view) {
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

Creature *FightPanel::selected = 0;

FightPanel::FightPanel() : playerSkillsView(0) {
    setZValue(5);
    setVisible(false);
}

FightPanel::FightPanel(const FightPanel &) : FightPanel() {}

QRectF FightPanel::boundingRect() const { return QRectF(0, 0, 400, 300); }

void FightPanel::paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *) {
    painter->fillRect(boundingRect(), QColor("BLACK"));
}

void FightPanel::setUpPanel(GameView *view) {
    Player *player = view->getScene()->getPlayer();
    PanelLists &lists = panelLists[this];
    copySkills(player, lists.skills);
    playerSkillsView = new PlayerListView(&lists.skills);
    playerSkillsView->setParentItem(this);
    playerSkillsView->setPos(0, boundingRect().height() - playerSkillsView->boundingRect().height());
}

void FightPanel::update() {
    GameScene *gameScene = dynamic_cast<GameScene *>(this->scene());
    if (gameScene && gameScene->getPlayer()) {
        copySkills(gameScene->getPlayer(), panelLists[this].skills);
        refresh(playerSkillsView);
    }
    QGraphicsItem::update();
}

void FightPanel::showPanel(GameView *view) {
    std::list<Creature *> *fightList = view->getScene()->getPlayer()->getFightList();
    if (!fightList->empty())
        selected = fightList->front();
    setVisible(true);
    setPos(view->mapToScene(view->width() / 2 - boundingRect().width() / 2,
                            view->height() / 2 - boundingRect().height() / 2));
    update();
}
