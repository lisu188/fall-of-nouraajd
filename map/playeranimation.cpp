#include "map.h"
#include "playeranimation.h"

#include <view/gamescene.h>
#include <view/gameview.h>
#include <view/playerstatsview.h>
#include <view/playerlistview.h>

PlayerAnimation::PlayerAnimation(QObject *parent) :
    QGraphicsItemAnimation(parent)
{
}

void PlayerAnimation::afterAnimationStep(qreal step)
{
    GameView *view=GameScene::getView();
    Player *player=GameScene::getPlayer();
    view->centerOn(this->item());
    player->update();
    if(step==1)
    {
        player->unLock();
        std::list<MapObject *> entered(*player->getEntered());
        for(std::list<MapObject *>::iterator it=entered.begin();
                it!=entered.end(); it++)
        {
            (*it)->onEnter();
            if(player!=GameScene::getPlayer()) {
                return;
            }
        }
        player->getEntered()->clear();
        if(player->getFightList()->size()>0)
        {
            view->showFightView();
        }
    }
}
