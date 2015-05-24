#include "CWrapper.h"

void CInteractionWrapper::performAction ( std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second ) {
    if ( auto f=this->get_override ( "performAction" ) ) {
        f ( first , second  );
    } else {
        this->CInteraction::performAction ( first,second );
    }
}

bool CInteractionWrapper::configureEffect ( std::shared_ptr<CEffect> effect ) {
    if ( auto f=this->get_override ( "configureEffect" ) ) {
        return f ( effect  );
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

void CPotionWrapper::onUse ( std::shared_ptr<CGameEvent> event ) {
    if ( auto f=this->get_override ( "onUse" ) ) {
        f (  event  );
    } else {
        this->CPotion::onUse ( event ) ;
    }
}

void CTriggerWrapper::trigger ( std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event ) {
    if ( auto f=this->get_override ( "trigger" ) ) {
        f (  object  , event );
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
