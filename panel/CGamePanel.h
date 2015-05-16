#pragma once

#include <QGraphicsItem>
#include "object/CObject.h"
#include <QWidget>

class CCreature;
class CGameView;
class CListView;
class CPlayerEquippedView;
class CCharPanel;
class CPlayerView;

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
    virtual void handleDrop ( CPlayerView* ,CGameObject * );
    bool isShown();
    CGameView *getView();
    virtual void mousePressEvent ( QGraphicsSceneMouseEvent * ) override;
    Q_INVOKABLE void setProperty ( QString name,QVariant property );
    Q_INVOKABLE QVariant property ( QString name ) const;
    Q_INVOKABLE void setStringProperty ( QString name,QString value );
    Q_INVOKABLE void setBoolProperty ( QString name,bool value );
    Q_INVOKABLE void setNumericProperty ( QString name,int value );
    Q_INVOKABLE QString getStringProperty ( QString name ) const;
    Q_INVOKABLE bool getBoolProperty ( QString name ) const;
    Q_INVOKABLE int getNumericProperty ( QString name ) const;
    Q_INVOKABLE void incProperty ( QString name,int value );
protected:
    CGameView *view=0;
};
