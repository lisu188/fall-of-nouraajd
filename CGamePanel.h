#pragma once
#include <QGraphicsItem>
#include "CReflection.h"
#include <QWidget>

class CCreature;
class CGameView;
class CPlayerListView;
class CPlayerEquippedView;
class CCharPanel;

class AGamePanel : public QGraphicsObject {
	Q_OBJECT
public:
	AGamePanel();
	AGamePanel ( const AGamePanel& );
	virtual void showPanel ();
	virtual void setUpPanel ( CGameView *view );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * );

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


class BackPackObject : public QWidget {
	Q_OBJECT
public:
	BackPackObject ( CGameView* view , CCharPanel *panel ) ;

protected:
	void mousePressEvent ( QMouseEvent * );
	void paintEvent ( QPaintEvent * );

private:
	CCharPanel *panel=0;
	QPixmap pixmap;
	int time = 0;
};

class CCharPanel : public AGamePanel {
	Q_OBJECT
public:
	CCharPanel();
	CCharPanel ( const CCharPanel& );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * );
	virtual void showPanel (  );
	virtual void setUpPanel ( CGameView *view );
private:
	CPlayerListView *playerInventoryView;
	CPlayerEquippedView *playerEquippedView;
	BackPackObject *backpack;
};

class CFightPanel : public AGamePanel {
	Q_OBJECT
public:
	CFightPanel();
	CFightPanel ( const CFightPanel& );
	static CCreature *selected;
	void update();
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * );
	virtual void showPanel ( );
	virtual void setUpPanel ( CGameView *view );
private:
	CPlayerListView *playerSkillsView;

};

class CTextPanel:public AGamePanel {
	Q_OBJECT
	Q_PROPERTY ( QString text READ getText WRITE setText USER true )
public:
	CTextPanel();
	CTextPanel ( const CTextPanel& );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
	virtual void showPanel (  );
	virtual void setUpPanel ( CGameView * view );
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent *event );
	QString getText() const;
	void setText ( const QString &value );

private:
	QString text;
};

