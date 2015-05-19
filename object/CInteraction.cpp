#include "CInteraction.h"
#include "CGame.h"
#include "object/CObject.h"
#include "handler/CHandler.h"
#include "panel/CPanel.h"
#include "handler/CHandler.h"

CInteraction::CInteraction() {
    setVisible ( false );
}

void CInteraction::onAction ( CCreature *first, CCreature *second ) {
    qDebug() << first->getObjectType()   << "used" << this->getObjectType()
             << "against" << second->getObjectType()  ;

    first->takeMana ( this->getManaCost() );

    this->performAction ( first , second  );

    if ( this->effect.length() >0 ) {
        CEffect *effect=getMap()->getObjectHandler()->createObject<CEffect*> ( this->effect );
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

void CInteraction::performAction ( CCreature *, CCreature * ) {

}

bool CInteraction::configureEffect ( CEffect * ) {
    return true;
}
