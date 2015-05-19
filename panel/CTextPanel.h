#pragma once
#include "CGamePanel.h"

class CTextPanel:public AGamePanel {
    Q_OBJECT
    Q_PROPERTY ( QString text READ getText WRITE setText USER true )
public:
    CTextPanel();
    virtual QRectF boundingRect() const override;
    virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * ) override;
    virtual void showPanel (  ) override;
    virtual void hidePanel() override;
    virtual void update() override;
    virtual void setUpPanel ( CGameView * view  ) override;
    virtual QString getPanelName() override;
    QString getText() const;
    void setText ( const QString &value );

private:
    QString text;
};
