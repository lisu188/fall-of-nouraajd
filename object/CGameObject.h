#pragma once

#include "CAnimatedObject.h"
#include "CUtil.h"

class CGameEvent;
class CMap;

class CGameObject : public CAnimatedObject {
    Q_OBJECT
    Q_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )
    Q_PROPERTY ( QString tooltip READ getTooltip WRITE setTooltip USER true )
public:
    CGameObject();
    QString getObjectType() const ;
    void setObjectType ( const QString &value ) ;

    CMap* getMap();
    void setMap ( CMap *map );

    Q_SIGNAL void mapChanged();

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

    virtual ~CGameObject() =0;
protected:
    virtual void hoverEnterEvent ( QGraphicsSceneHoverEvent *event ) override final ;
    virtual void hoverLeaveEvent ( QGraphicsSceneHoverEvent *event ) override final;
    virtual void mousePressEvent ( QGraphicsSceneMouseEvent * ) override final;
    bool hasTooltip=true;
private:
    QString tooltip;
    QGraphicsSimpleTextItem statsView;
    CMap *map=nullptr;
    QString objectType;
};

class Visitable {
public:
    virtual void onEnter ( CGameEvent * ) =0;
    virtual void onLeave ( CGameEvent * ) =0;
};

class Moveable {
public:
    virtual Coords getNextMove() =0;
    virtual void beforeMove() =0;
    virtual void afterMove() =0;
};

class Wearable {
public:
    virtual void onEquip ( CGameEvent * ) =0;
    virtual void onUnequip ( CGameEvent * ) =0;
};

class Usable {
public:
    virtual void onUse ( CGameEvent * ) =0;
};

class Turnable {
public:
    virtual void onTurn ( CGameEvent * ) =0;
};

class Creatable {
public:
    virtual void onCreate ( CGameEvent * ) =0;
    virtual void onDestroy ( CGameEvent * ) =0;
};
