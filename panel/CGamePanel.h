#pragma once

#include <QGraphicsItem>
#include "CReflection.h"
#include "object/CObject.h"
#include <QWidget>

class CCreature;
class CGameView;
class CListView;
class CPlayerEquippedView;
class CCharPanel;

class AGamePanel : public QGraphicsObject {
	Q_OBJECT

	friend class CGuiHandler;
public:
	virtual void showPanel() =0;
	virtual void hidePanel() =0;
	virtual void update() =0;
	virtual void setUpPanel ( CGameView * ) =0;
	virtual QRectF boundingRect() const=0;
	virtual void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * ) =0;
	virtual QString getPanelName() =0;
	bool isShown() {
		return this->isVisible();
	}
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent * ) override {
		this->hidePanel ( );
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
protected:
	CGameView *view=0;
};
