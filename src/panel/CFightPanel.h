//#pragma once
//
//#include "CGamePanel.h"
//
//class CCreature;
//
//class CFightPanel;
//
//class CListView;
//
//class CCreatureFightView : public CGameObject {
//
//
//    friend class CFightPanel;
//
//public:
//    CCreatureFightView();
//
//    void setCreature ( std::shared_ptr<CCreature> creature );
//
//    virtual QRectF boundingRect() const;
//
//    virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
//
//private:
//    std::shared_ptr<CCreature> creature;
//};
//
//class CFightPanel : public AGamePanel {
//
//public:
//    CFightPanel();
//
//    virtual void update() override;
//
//    virtual QRectF boundingRect() const override;
//
//    virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *,
//                         QWidget * ) override;
//
//    virtual void showPanel() override;
//
//    virtual void setUpPanel ( std::shared_ptr<CGameView> view ) override;
//
//    virtual void hidePanel() override;
//
//    virtual std::string getPanelName() override;
//
//    virtual void onClickAction ( std::shared_ptr<CGameObject> object ) override;
//
//private:
//    std::shared_ptr<CListView> playerSkillsView;
//    std::shared_ptr<CCreatureFightView> fightView;
//};
//
//
