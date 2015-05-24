#pragma once
#include <string>
#include <functional>
#include <map>
#include"CMap.h"
class CCreature;
class QGraphicsSceneMouseEvent;
class Stats;
class CEffect;

class CInteraction : public CGameObject {
    Q_OBJECT
    Q_PROPERTY ( int manaCost READ getManaCost  WRITE setManaCost USER true )
    Q_PROPERTY ( QString effect READ getEffect WRITE setEffect USER true )
public:
    CInteraction();
    ~CInteraction();
    void onAction ( std::shared_ptr<CCreature> first,std::shared_ptr<CCreature>  second );
    virtual void performAction ( std::shared_ptr<CCreature>, std::shared_ptr<CCreature> );
    virtual bool configureEffect ( std::shared_ptr<CEffect> );

    QString getEffect() const;
    void setEffect ( const QString &value );

    int getManaCost() const;
    void setManaCost ( int value );

    int manaCost;
    QString effect;
private:
    QGraphicsSimpleTextItem statsView;
};


