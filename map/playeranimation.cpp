#include "map.h"
#include "playeranimation.h"

#include <view/gamescene.h>
#include <view/gameview.h>
#include <view/playerstatsview.h>
#include <view/playerlistview.h>

PlayerAnimation::PlayerAnimation(QObject *parent)
		: QGraphicsItemAnimation(parent) {
}

void PlayerAnimation::afterAnimationStep(qreal step) {
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
