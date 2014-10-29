#pragma once
#include <QGraphicsItem>
#include "CReflection.h"
#include "CMapObject.h"
#include <QWidget>

class CCreature;
class CGameView;
class CPlayerListView;
class CPlayerEquippedView;
class CCharPanel;

class AGamePanel : public CGameObject {
	Q_OBJECT

	friend class CGuiHandler;
public:
	AGamePanel();
	AGamePanel ( const AGamePanel& );
	virtual void showPanel ();
	virtual void hidePanel();
	virtual void update();
	bool isShown();
    virtual QString getPanelName();
	virtual void setUpPanel ( CGameView * );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * );

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
    QString getPanelName() override;
    void hidePanel() override;
	CCharPanel();
	CCharPanel ( const CCharPanel& );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
	                     QWidget * );
	virtual void showPanel (  );
	virtual void setUpPanel ( CGameView *view );
	virtual void update();
private:
	CPlayerListView *playerInventoryView = nullptr;
	CPlayerEquippedView *playerEquippedView = nullptr;
	BackPackObject *backpack = nullptr;
};

class CFightPanel : public AGamePanel {
	Q_OBJECT
public:
	CFightPanel();
	CFightPanel ( const CFightPanel& );

	virtual void update();
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
    QString getPanelName() override;
    void hidePanel() override;
    void update() override;
	CTextPanel();
	CTextPanel ( const CTextPanel& );
	virtual QRectF boundingRect() const;
	virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
	virtual void showPanel (  );
	virtual void setUpPanel ( CGameView * view );
	virtual void mousePressEvent ( QGraphicsSceneMouseEvent * );
	QString getText() const;
	void setText ( const QString &value );

private:
	QString text;
};

