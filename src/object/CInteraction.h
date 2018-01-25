#pragma once

#include "core/CGlobal.h"
#include "object/CGameObject.h"

class CCreature;

class QGraphicsSceneMouseEvent;

class Stats;

class CEffect;

class CInteraction : public CGameObject {

V_META(CInteraction, CGameObject,
       V_PROPERTY(CInteraction, std::shared_ptr<CEffect>, effect, getEffect, setEffect),
       V_PROPERTY(CInteraction, int, manaCost, getManaCost, setManaCost)
)

public:
    CInteraction();

    ~CInteraction();

    void onAction(std::shared_ptr<CCreature> first, std::shared_ptr<CCreature> second);

    virtual void performAction(std::shared_ptr<CCreature>, std::shared_ptr<CCreature>);

    virtual bool configureEffect(std::shared_ptr<CEffect>);

    std::shared_ptr<CEffect> getEffect() const;

    void setEffect(const std::shared_ptr<CEffect> value);

    int getManaCost() const;

    void setManaCost(int value);

private:
    int manaCost = 0;
    std::shared_ptr<CEffect> effect;
};



