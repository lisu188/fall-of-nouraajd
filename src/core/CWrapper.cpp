#include "CWrapper.h"

void CInteractionWrapper::performAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second) {
    if (auto f = this->get_override("performAction")) {
        PY_SAFE (f(first, second);)
    } else {
        this->CInteraction::performAction(first, second);
    }
}

bool CInteractionWrapper::configureEffect(std::shared_ptr<CEffect> effect) {
    if (auto f = this->get_override("configureEffect")) {
        PY_SAFE_RET_VAL (return f(effect);, false)
    } else {
        return this->CInteraction::configureEffect(effect);
    }
}

bool CEffectWrapper::onEffect() {
    if (auto f = this->get_override("onEffect")) {
        PY_SAFE_RET_VAL (return f();, false)
    } else {
        return this->CEffect::onEffect();
    }
}

void CTileWrapper::onStep(std::shared_ptr<CCreature> creature) {
    if (auto f = this->get_override("onStep")) {
        PY_SAFE (f(creature);)
    } else {
        this->CTile::onStep(creature);
    }
}

void CPotionWrapper::onUse(std::shared_ptr<CGameEvent> event) {
    if (auto f = this->get_override("onUse")) {
        PY_SAFE (f(event);)
    } else {
        this->CPotion::onUse(event);
    }
}

void CTriggerWrapper::trigger(std::shared_ptr<CGameObject> object, std::shared_ptr<CGameEvent> event) {
    if (auto f = this->get_override("trigger")) {
        PY_SAFE (f(object, event);)
    } else {
        this->CTrigger::trigger(object, event);
    }
}

bool CQuestWrapper::isCompleted() {
    if (auto f = this->get_override("isCompleted")) {
        PY_SAFE_RET_VAL (return f();, false)
    } else {
        return this->CQuest::isCompleted();
    }
}

void CQuestWrapper::onComplete() {
    if (auto f = this->get_override("onComplete")) {
        PY_SAFE (f();)
    } else {
        this->CQuest::onComplete();
    }
}

void  CPluginWrapper::load(std::shared_ptr<CGame> game) {
    if (auto f = this->get_override("load")) {
        PY_SAFE (f(game);)
    } else {
        this->CPlugin::load(game);
    }
}

void  CMapPluginWrapper::load(std::shared_ptr<CMap> map) {
    if (auto f = this->get_override("load")) {
        PY_SAFE (f(map);)
    } else {
        this->CMapPlugin::load(map);
    }
}