#pragma once
#include "CAnimatedObject.h"
#include "Util.h"

class CMap;
class CMapObject : public CAnimatedObject {
	friend class CObjectHandler;
	Q_OBJECT
	Q_PROPERTY ( QString typeName READ getTypeName WRITE setTypeName USER true )
	Q_PROPERTY ( QString tooltip READ getTooltip WRITE setTooltip USER true )
public:
	CMapObject();
	virtual ~CMapObject();
	int posx=0, posy=0, posz=0;
	virtual void moveTo ( int x, int y, int z );
	int getPosX() const;
	int getPosY() const;
	int getPosZ() const;
	virtual void onEnter();
	virtual void onMove();
	virtual void onCreate();
	virtual void onDestroy();
	Q_SLOT void move ( int x, int y );
	void setMap ( CMap *map );
	CMap *getMap();
	void setVisible ( bool vis );
	Coords getCoords();
	void setCoords ( Coords coords );
	void setNumber ( int i, int x );
	QString getTypeName() const;
	void setTypeName ( const QString &value );
	QString getTooltip() const;
	void setTooltip ( const QString &value );

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
	CMap *map=0;
	QString typeName;
};

class CEvent : public CMapObject {
	Q_OBJECT
	Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
public:
	CEvent();
	CEvent ( const CEvent & );

	bool isEnabled();
	void setEnabled ( bool enabled );

private:
    bool enabled = true;
    void setClass(const QString &value);
};
