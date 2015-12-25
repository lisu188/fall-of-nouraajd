#pragma once

#include "CGamePanel.h"

class CCharPanel : public AGamePanel {
Q_OBJECT
public:
    CCharPanel();

    virtual QRectF boundingRect() const override;

    virtual void paint(QPainter *painter, const QStyleOptionGraphicsItem *,
                       QWidget *) override;

    virtual void showPanel() override;

    virtual void hidePanel() override;

    virtual void setUpPanel(std::shared_ptr<CGameView> view) override;

    virtual void update() override;

    virtual QString getPanelName() override;

    virtual void onClickAction(std::shared_ptr<CGameObject> object) override;

    virtual void handleDrop(std::shared_ptr<CPlayerView> view, std::shared_ptr<CGameObject> object) override;

private:
    std::shared_ptr<CListView> playerInventoryView;
    std::shared_ptr<CPlayerEquippedView> playerEquippedView;
};
