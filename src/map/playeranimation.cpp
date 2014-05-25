#include "map.h"
#include "playeranimation.h"

#include <src/view/gamescene.h>
#include <src/view/gameview.h>
#include <src/view/playerstatsview.h>
#include <src/view/playerlistview.h>

PlayerAnimation::PlayerAnimation(QObject *parent) :
    QGraphicsItemAnimation(parent)
{
}

void PlayerAnimation::afterAnimationStep(qreal step)
{
    Player *player = GameScene::getPlayer();
    GameView *view = GameScene::getView();
    view->centerOn(player);
    if (step >= 1) {
        std::list<MapObject *> entered(*player->getEntered());
        for (std::list<MapObject *>::iterator it = entered.begin();
             it != entered.end(); it++) {
            (*it)->onEnter();
            if (player != GameScene::getPlayer()) {
                return;
            }
        }
        player->getEntered()->clear();
        if (player->getFightList()->size() > 0) {
            view->showFightView();
        }
    }
}
