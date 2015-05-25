#pragma once
#include "CGlobal.h"
#include "object/CObject.h"
#include "handler/CHandler.h"

class CCreature;
class CGameView;
class CListView;
class CPlayerEquippedView;
class CCharPanel;
class CPlayerView;

class AGamePanel : public CGameObject,public CClickAction {
    Q_OBJECT
    friend class CGuiHandler;
public:
    AGamePanel();
    virtual ~AGamePanel();
    virtual void showPanel() =0;
    virtual void hidePanel() =0;
    virtual void update() =0;
    virtual void setUpPanel ( std::shared_ptr<CGameView> ) =0;
    virtual void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * ) =0;
    virtual QString getPanelName() =0;
    virtual void handleDrop ( std::shared_ptr<CPlayerView> , std::shared_ptr<CGameObject> );
    virtual void onClickAction ( std::shared_ptr<CGameObject> ) override;
    bool isShown();
    std::shared_ptr<CGameView> getView();

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
    std::weak_ptr<CGameView> view;
};


