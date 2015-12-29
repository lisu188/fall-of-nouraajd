#pragma once

#include "core/CGlobal.h"
#include "object/CObject.h"

class CInteractionWrapper : public CInteraction, public boost::python::wrapper<CInteractionWrapper> {
public:
    virtual void performAction ( std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second ) override final;

    virtual bool configureEffect ( std::shared_ptr<CEffect> effect ) override final;
};

class CEffectWrapper : public CEffect, public boost::python::wrapper<CEffectWrapper> {
public:
    virtual bool onEffect() override final;
};

class CTileWrapper : public CTile, public boost::python::wrapper<CTileWrapper> {
public:
    virtual void onStep ( std::shared_ptr<CCreature> creature ) override final;
};

class CPotionWrapper : public CPotion, public boost::python::wrapper<CPotionWrapper> {
public:
    virtual void onUse ( std::shared_ptr<CGameEvent> event ) override final;
};

class CTriggerWrapper : public CTrigger, public boost::python::wrapper<CTriggerWrapper> {
public:
    virtual void trigger ( std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event ) override final;
};

class CQuestWrapper : public CQuest, public boost::python::wrapper<CQuestWrapper> {
public:
    virtual bool isCompleted() override final;

    virtual void onComplete() override final;
};

template<class T>
class CWrapper : public T, public boost::python::wrapper<CWrapper<T>> {
public:
    virtual void onEnter ( std::shared_ptr<CGameEvent> event ) override final {
        if ( auto f = this->get_override ( "onEnter" ) ) {
            PY_SAFE ( f ( event ); )
        } else {
            this->T::onEnter ( event );
        }
    }

    virtual void onTurn ( std::shared_ptr<CGameEvent> event ) override final {
        if ( auto f = this->get_override ( "onTurn" ) ) {
            PY_SAFE ( f ( event ); )
        } else {
            this->T::onTurn ( event );
        }
    }

    virtual void onCreate ( std::shared_ptr<CGameEvent> event ) override final {
        if ( auto f = this->get_override ( "onCreate" ) ) {
            PY_SAFE ( f ( event ); )
        } else {
            this->T::onCreate ( event );
        }
    }

    virtual void onDestroy ( std::shared_ptr<CGameEvent> event ) override final {
        if ( auto f = this->get_override ( "onDestroy" ) ) {
            PY_SAFE ( f ( event ); )
        } else {
            this->T::onDestroy ( event );
        }
    }

    virtual void onLeave ( std::shared_ptr<CGameEvent> event ) override final {
        if ( auto f = this->get_override ( "onLeave" ) ) {
            PY_SAFE ( f ( event ); )
        } else {
            this->T::onLeave ( event );
        }
    }
};
