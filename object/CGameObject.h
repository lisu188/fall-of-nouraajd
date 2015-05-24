#pragma once

#include "CAnimatedObject.h"
#include "CUtil.h"

class CGameEvent;
class CMap;

class CGameObject : public CAnimatedObject,public std::enable_shared_from_this<CGameObject> {
    Q_OBJECT
    Q_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )
    Q_PROPERTY ( QString tooltip READ getTooltip WRITE setTooltip USER true )
public:
    CGameObject();
    virtual ~CGameObject() ;

    QString getObjectType() const ;
    void setObjectType ( const QString &value ) ;

    std::shared_ptr<CMap> getMap();
    void setMap ( std::shared_ptr<CMap> map );

    template<typename T=CGameObject>
    std::shared_ptr<T> ptr() {
        return cast<T> ( shared_from_this() );
    }

    Q_INVOKABLE void setProperty ( QString name,QVariant property ) {
        QByteArray byteArray = name.toUtf8();
        const char* cString = byteArray.constData();
        this->QObject::setProperty ( cString,property );
    }
    Q_INVOKABLE QVariant property ( QString name ) const {
        QByteArray byteArray = name.toUtf8();
        const char* cString = byteArray.constData();
        return this->QObject::property ( cString );
    }
    Q_INVOKABLE void setStringProperty ( QString name,QString value ) {
        this->setProperty ( name, value ) ;
    }
    Q_INVOKABLE void setBoolProperty ( QString name,bool value ) {
        this->setProperty ( name,value );
    }
    Q_INVOKABLE void setNumericProperty ( QString name,int value ) {
        this->setProperty ( name,value );
    }
    Q_INVOKABLE QString getStringProperty ( QString name ) const {
        return this->property ( name ).toString();
    }
    Q_INVOKABLE bool getBoolProperty ( QString name ) const {
        return this->property ( name ).toBool();
    }
    Q_INVOKABLE int getNumericProperty ( QString name ) const {
        return this->property ( name ).toInt();
    }
    Q_INVOKABLE void incProperty ( QString name,int value ) {
        this->setNumericProperty ( name,this->getNumericProperty ( name )+value );
    }

    virtual QString getTooltip() const;
    virtual void setTooltip ( const QString &value );

    void setVisible ( bool vis );

    void drag();
protected:
    virtual void hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) override final ;
    virtual void hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) override final;
    virtual void mousePressEvent ( QGraphicsSceneMouseEvent * ) override final;
    bool hasTooltip=true;
private:
    QString tooltip;
    QString objectType;
    QGraphicsSimpleTextItem statsView;
    std::weak_ptr<CMap> map;
};

class Visitable {
public:
    virtual void onEnter ( std::shared_ptr<CGameEvent> ) =0;
    virtual void onLeave ( std::shared_ptr<CGameEvent> ) =0;
};

class Moveable {
public:
    virtual Coords getNextMove() =0;
    virtual void beforeMove() =0;
    virtual void afterMove() =0;
};

class Wearable {
public:
    virtual void onEquip ( std::shared_ptr<CGameEvent> ) =0;
    virtual void onUnequip ( std::shared_ptr<CGameEvent> ) =0;
};

class Usable {
public:
    virtual void onUse ( std::shared_ptr<CGameEvent> ) =0;
};

class Turnable {
public:
    virtual void onTurn ( std::shared_ptr<CGameEvent> ) =0;
};

class Creatable {
public:
    virtual void onCreate ( std::shared_ptr<CGameEvent> ) =0;
    virtual void onDestroy ( std::shared_ptr<CGameEvent> ) =0;
};
