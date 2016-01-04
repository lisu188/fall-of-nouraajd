#pragma once

#include "CGamePanel.h"

class CTextPanel : public AGamePanel {

    Q_PROPERTY ( std::string text
                 READ
                 getText
                 WRITE
                 setText
                 USER
                 true )
public:
    CTextPanel();

    virtual QRectF boundingRect() const override;

    virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * ) override;

    virtual void showPanel() override;

    virtual void hidePanel() override;

    virtual void update() override;

    virtual void setUpPanel ( std::shared_ptr<CGameView> view ) override;

    virtual std::string getPanelName() override;

    std::string getText() const;

    void setText ( const std::string &value );

private:
    std::string text;
};
