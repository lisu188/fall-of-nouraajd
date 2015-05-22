#include "CWrapper.h"

void CInteractionWrapper::performAction ( CCreature *first, CCreature *second ) {
    if ( auto f=this->get_override ( "performAction" ) ) {
        f ( boost::ref ( first ),boost::ref ( second ) );
    } else {
        this->CInteraction::performAction ( first,second );
    }
}

bool CInteractionWrapper::configureEffect ( CEffect *effect ) {
    if ( auto f=this->get_override ( "configureEffect" ) ) {
        return f ( boost::ref ( effect ) );
    } else {
        return this->CInteraction::configureEffect ( effect );
    }
}

bool CEffectWrapper::onEffect() {
    if ( auto f=this->get_override ( "onEffect" ) ) {
        return f ();
    } else {
        return this->CEffect::onEffect() ;
    }
}

void CTileWrapper::onStep ( CCreature *creature ) {
    if ( auto f=this->get_override ( "onStep" ) ) {
        f ( boost::ref ( creature ) );
    } else {
        this->CTile::onStep ( creature ) ;
    }
}

void CPotionWrapper::onUse ( CGameEvent *event ) {
    if ( auto f=this->get_override ( "onUse" ) ) {
        f ( boost::ref ( event ) );
    } else {
        this->CPotion::onUse ( event ) ;
    }
}

void CTriggerWrapper::trigger ( CGameObject *object, CGameEvent *event ) {
    if ( auto f=this->get_override ( "trigger" ) ) {
        f ( boost::ref ( object ) ,boost::ref ( event ) );
    } else {
        this->CTrigger::trigger ( object,event ) ;
    }
}

bool CQuestWrapper::isCompleted() {
    if ( auto f=this->get_override ( "isCompleted" ) ) {
        return f();
    } else {
        return this->CQuest::isCompleted();
    }
}

void CQuestWrapper::onComplete() {
    if ( auto f=this->get_override ( "onComplete" ) ) {
        f();
    } else {
        this->CQuest::onComplete();
    }
}
