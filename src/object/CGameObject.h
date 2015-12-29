#pragma once

#include "core/CUtil.h"
#include "CAnimatedObject.h"
#include "vstd.h"

class CGameEvent;

class CMap;

class CGameObject : public CAnimatedObject, public std::enable_shared_from_this<CGameObject> {
    Q_OBJECT
    Q_PROPERTY ( QString objectType
                 READ
                 getObjectType
                 WRITE
                 setObjectType
                 USER
                 true )
    Q_PROPERTY ( QString tooltip
                 READ
                 getTooltip
                 WRITE
                 setTooltip
                 USER
                 true )
public:
    CGameObject();

    virtual ~CGameObject();

    QString getObjectType() const;

    void setObjectType ( const QString &value );

    std::shared_ptr<CMap> getMap();

    void setMap ( std::shared_ptr<CMap> map );

    template<typename T=CGameObject>
    std::shared_ptr<T> ptr() {
        return vstd::cast<T> ( shared_from_this() );
    }

    void setProperty ( QString name, QVariant property );

    QVariant property ( QString name ) const;

    void setStringProperty ( QString name, QString value );

    void setBoolProperty ( QString name, bool value );

    void setNumericProperty ( QString name, int value );

    QString getStringProperty ( QString name ) const;

    bool getBoolProperty ( QString name ) const;

    int getNumericProperty ( QString name ) const;

    template<typename T=CGameObject>
    void setObjectProperty ( QString name, std::shared_ptr<T> object ) {
        setProperty ( name, QVariant::fromValue ( object ) );
    }

    template<typename T=CGameObject>
    std::shared_ptr<T> getObjectProperty ( QString name ) {
        return *reinterpret_cast<std::shared_ptr<T> *> ( property ( name ).data() );
    }

    void incProperty ( QString name, int value );

    virtual QString getTooltip() const;

    virtual void setTooltip ( const QString &value );

    void setVisible ( bool vis );

    void drag();

protected:
    virtual void hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) override final;

    virtual void hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) override final;

    virtual void mousePressEvent ( QGraphicsSceneMouseEvent * ) override final;

    bool hasTooltip = true;
private:
    QString tooltip;
    QString objectType;
    QGraphicsSimpleTextItem statsView;
    std::weak_ptr<CMap> map;
};

GAME_PROPERTY ( CGameObject )

class Visitable {
public:
    virtual void onEnter ( std::shared_ptr<CGameEvent> ) = 0;

    virtual void onLeave ( std::shared_ptr<CGameEvent> ) = 0;
};

class Moveable {
public:
    virtual Coords getNextMove() = 0;

    virtual void beforeMove() = 0;

    virtual void afterMove() = 0;
};

class Wearable {
public:
    virtual void onEquip ( std::shared_ptr<CGameEvent> ) = 0;

    virtual void onUnequip ( std::shared_ptr<CGameEvent> ) = 0;
};

class Usable {
public:
    virtual void onUse ( std::shared_ptr<CGameEvent> ) = 0;
};

class Turnable {
public:
    virtual void onTurn ( std::shared_ptr<CGameEvent> ) = 0;
};

class Creatable {
public:
    virtual void onCreate ( std::shared_ptr<CGameEvent> ) = 0;

    virtual void onDestroy ( std::shared_ptr<CGameEvent> ) = 0;
};
