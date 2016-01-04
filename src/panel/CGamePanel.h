#pragma once

#include "core/CGlobal.h"
#include "object/CObject.h"
#include "handler/CHandler.h"

class CCreature;

class CGameView;

class CListView;

class CPlayerEquippedView;

class CCharPanel;

class CPlayerView;

class AGamePanel : public CGameObject, public CClickAction {
    Q_OBJECT

    friend class CGuiHandler;

public:
    AGamePanel();

    virtual ~AGamePanel();

    virtual void showPanel() = 0;

    virtual void hidePanel() = 0;

    virtual void update() = 0;

    virtual void setUpPanel ( std::shared_ptr<CGameView> ) = 0;

    virtual void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * ) = 0;

    virtual std::string getPanelName() = 0;

    virtual void handleDrop ( std::shared_ptr<CPlayerView>, std::shared_ptr<CGameObject> );

    virtual void onClickAction ( std::shared_ptr<CGameObject> ) override;

    bool isShown();

    std::shared_ptr<CGameView> getView();

protected:
    std::weak_ptr<CGameView> view;
};


