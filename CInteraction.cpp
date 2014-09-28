#include "CInteraction.h"
#include "CCreature.h"
#include "CGameScene.h"
#include "CGameView.h"
#include  "CPlayerView.h"
#include <QDebug>
#include "CItem.h"
#include "CCreature.h"
#include "CConfigurationProvider.h"
#include "CGamePanel.h"
#include "CObjectHandler.h"

CInteraction::CInteraction() { setVisible ( false ); }

CInteraction::CInteraction ( const CInteraction & ) {}

void CInteraction::onAction ( CCreature *first, CCreature *second ) {
	qDebug() << first->getTypeName()   << "used" << this->getTypeName()
	         << "against" << second->getTypeName()  ;
	this->performAction ( first , second  );

	if ( this->effect.length() >0 ) {
		CEffect *effect=getMap()->getObjectHandler()->createMapObject<CEffect*> ( this->effect );
		effect->setCaster ( first );
		if ( this->configureEffect ( effect  ) ) {
			CCreature *victim;
			if ( effect->isBuff() ) {
				victim=first;
			} else {
				victim=second;
			}
			effect->setVictim ( victim );
			victim->addEffect ( effect );
		}
	}
}

void CInteraction::mousePressEvent ( QGraphicsSceneMouseEvent * ) {
	CPlayer *player =this->getMap()->getScene()->getPlayer();
	if ( player->getFightList()->size() == 0 ) {
		return;
	}
	if ( manaCost > player->getMana() ) {
		return;
	}
	CCreature *creature = CFightPanel::selected;
	if ( !creature ) {
		return;
	}
	player->performAction ( this, creature );
}

int CInteraction::getManaCost() const {
	return manaCost;
}

void CInteraction::setManaCost ( int value ) {
	manaCost = value;
}

QString CInteraction::getEffect() const {
	return effect;
}

void CInteraction::setEffect ( const QString &value ) {
	effect = value;
}

CEffect::CEffect() {

}

CEffect::CEffect ( const CEffect & ) {

}

int CEffect::getTimeLeft() {
	return timeLeft;
}

int CEffect::getTimeTotal() {
	return timeTotal;
}

CCreature *CEffect::getCaster() {
	return caster;
}

CCreature *CEffect::getVictim() {
	return victim;
}

bool CEffect::apply ( CCreature *creature ) {
	if ( bonus )
		if ( timeTotal == timeLeft ) {
			creature->addBonus ( *bonus );
		}
	timeLeft--;
	if ( timeLeft == 0 ) {
		if ( bonus ) {
			creature->removeBonus ( *bonus );
		}
		return false;
	}
	return onEffect();
}

Stats *CEffect::getBonus() {
	return bonus;
}

void CEffect::setBonus ( Stats *value ) {
	bonus = value;
}

int CEffect::getDuration() {
	return duration;
}

void CEffect::setDuration ( int duration ) {
	this->duration=duration;
	timeLeft = timeTotal =duration;
}

bool CEffect::onEffect() {
	return false;
}

bool CEffect::isBuff() const {
	return buff;
}

void CEffect::setBuff ( bool value ) {
	buff = value;
}

void CEffect::setCaster ( CCreature *value ) {
	caster = value;
}

void CEffect::setVictim ( CCreature *value ) {
	victim = value;
}

void CInteraction::performAction ( CCreature *, CCreature * ) {

}

bool CInteraction::configureEffect ( CEffect * ) {
	return true;
}
