#pragma once

#include "core/CGlobal.h"
#include "core/CMap.h"

class CCreature;

class QGraphicsSceneMouseEvent;

class Stats;

class CEffect;

class CInteraction : public CGameObject {
Q_OBJECT
    Q_PROPERTY(int manaCost
                       READ
                               getManaCost
                       WRITE
                       setManaCost USER

                       true)
    Q_PROPERTY (std::shared_ptr<CEffect>
                        effect READ
                        getEffect WRITE
                        setEffect USER
                        true)
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
    int manaCost;
    std::shared_ptr<CEffect> effect;
};

GAME_PROPERTY (CInteraction)

