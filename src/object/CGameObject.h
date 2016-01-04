#pragma once

#include "core/CUtil.h"
#include "core/CDefines.h"
#include "vstd.h"

class CGameEvent;

class CMap;

class CGameObject : public std::enable_shared_from_this<CGameObject> {

    Q_PROPERTY ( std::string objectType
                 READ
                 getObjectType
                 WRITE
                 setObjectType
                 USER
                 true )
    Q_PROPERTY ( std::string tooltip
                 READ
                 getTooltip
                 WRITE
                 setTooltip
                 USER
                 true )
public:
    CGameObject();

    virtual ~CGameObject();

    std::string getObjectType() const;

    void setObjectType ( const std::string &value );

    std::shared_ptr<CMap> getMap();

    void setMap ( std::shared_ptr<CMap> map );

    template<typename T=CGameObject>
    std::shared_ptr<T> ptr() {
        return vstd::cast<T> ( shared_from_this() );
    }

    void setProperty ( std::string name, QVariant property );

    QVariant property ( std::string name ) const;

    void setStringProperty ( std::string name, std::string value );

    void setBoolProperty ( std::string name, bool value );

    void setNumericProperty ( std::string name, int value );

    std::string getStringProperty ( std::string name ) const;

    bool getBoolProperty ( std::string name ) const;

    int getNumericProperty ( std::string name ) const;

    template<typename T=CGameObject>
    void setObjectProperty ( std::string name, std::shared_ptr<T> object ) {
        setProperty ( name, QVariant::fromValue ( object ) );
    }

    template<typename T=CGameObject>
    std::shared_ptr<T> getObjectProperty ( std::string name ) {
        return *reinterpret_cast<std::shared_ptr<T> *> ( property ( name ).data() );
    }

    void incProperty ( std::string name, int value );

    virtual std::string getTooltip() const;

    virtual void setTooltip ( const std::string &value );

    void setVisible ( bool vis );

    void drag();

protected:
    //TODO: tooltip
//    virtual void hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) override final;
//
//    virtual void hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) override final;
//
//    virtual void mousePressEvent ( QGraphicsSceneMouseEvent * ) override final;

    bool hasTooltip = true;
private:
    std::string tooltip;
    std::string objectType;
    //TODO: tooltip
    //QGraphicsSimpleTextItem statsView;
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
