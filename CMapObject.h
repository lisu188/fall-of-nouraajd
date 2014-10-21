#pragma once
#include "CAnimatedObject.h"
#include "Util.h"
class CGameEvent;
class CMap;
class CCreature;

class Visitable {
public:
	virtual void onEnter ( CGameEvent * ) =0;
	virtual void onLeave ( CGameEvent * ) =0;
};

class Moveable {
public:
	virtual Coords getNextMove() =0;
//    virtual void beforeMove()=0;
//    virtual void afterMove()=0;
};

class Wearable {
	virtual void onEquip ( CCreature *creature ) =0;
	virtual void onUnequip ( CCreature *creature ) =0;
};

class Usable {
	virtual void onUse ( CCreature *creature ) =0;
};

class CMapObject : public CAnimatedObject {
	friend class CObjectHandler;
	Q_OBJECT
	Q_PROPERTY ( QString objectType READ getObjectType WRITE setObjectType USER true )
	Q_PROPERTY ( QString tooltip READ getTooltip WRITE setTooltip USER true )
public:
	CMapObject();
	virtual ~CMapObject();
	int posx=0, posy=0, posz=0;
	int getPosX() const;
	int getPosY() const;
	int getPosZ() const;

	virtual void onTurn ( CGameEvent * );

	virtual void onCreate ( CGameEvent * );
	virtual void onDestroy ( CGameEvent * );

	void setMap ( CMap *map );
	CMap *getMap();
	void setVisible ( bool vis );
	Coords getCoords();
	void setCoords ( Coords coords );
	QString getObjectType() const;
	void setObjectType ( const QString &value );
	QString getTooltip() const;
	void setTooltip ( const QString &value );
	virtual void move ( int x, int y , int z );
	void move ( Coords coords );
	void moveTo ( int x, int y, int z );
	void moveTo ( Coords coords );

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

protected:
	QString tooltip;
	virtual void hoverEnterEvent ( QGraphicsSceneHoverEvent *event );
	virtual void hoverLeaveEvent ( QGraphicsSceneHoverEvent *event );
	//QGraphicsSimpleTextItem statsView;
private:
	CMap *map=nullptr;
	QString objectType;
};

class CEvent : public CMapObject,public Visitable {
	Q_OBJECT
	Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
	Q_PROPERTY ( QString eventClass READ getEventClass WRITE setEventClass USER true )
public:
	CEvent();
	CEvent ( const CEvent & );

	bool isEnabled();
	void setEnabled ( bool enabled );
	QString getEventClass();
	void setEventClass ( const QString &value );

	virtual void onEnter ( CGameEvent * );
	virtual void onLeave ( CGameEvent * );
private:
	QString eventClass;
	bool enabled = true;
};
