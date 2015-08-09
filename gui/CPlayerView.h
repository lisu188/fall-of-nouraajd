#pragma once
#include "CGlobal.h"
#include "object/CObject.h"

class CMapObject;
class CMap;
class QPaintEvent;
class CPlayer;
class CItem;
class CItemSlot;
class CGameView;
class CTradePanel;

class CPlayerView: public CGameObject {
    Q_OBJECT
public:
    CPlayerView ( std::shared_ptr<AGamePanel> panel );
protected:
    virtual void dropEvent ( QGraphicsSceneDragDropEvent *event );
    std::weak_ptr<AGamePanel> panel;
};

class CPlayerEquippedView : public CPlayerView {
    Q_OBJECT
public:
    CPlayerEquippedView ( std::shared_ptr<AGamePanel> panel );
    QRectF boundingRect() const;
    void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * );
    void update();
private:
    std::list<std::shared_ptr<CItemSlot>> itemSlots;
};

class PlayerStatsView : public QWidget {
    Q_OBJECT
public:
    explicit PlayerStatsView();
    void setPlayer ( std::shared_ptr<CPlayer> value );
    void update();
protected:
    void paintEvent ( QPaintEvent * );

private:
    std::shared_ptr<CPlayer> player;
};

class CScrollObject;
class CListView : public CPlayerView {
    Q_OBJECT
    friend class CScrollObject;
public:
    CListView ( std::shared_ptr<AGamePanel> panel );
    virtual QRectF boundingRect() const;
    virtual void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
    void updatePosition ( int i );
    void setXY ( int x, int y );
    void update();
protected:
    virtual std::set<std::shared_ptr<CGameObject>> getItems() const=0;
private:
    void setNumber ( std::shared_ptr<CGameObject> item, int i, int x );
    unsigned int curPosition;
    unsigned int x, y;
    std::shared_ptr<CScrollObject> right,left;
    std::set<std::shared_ptr<CGameObject>> items;
    QPixmap pixmap;
};

class CPlayerInventoryView:public CListView {
    Q_OBJECT
public:
    CPlayerInventoryView ( std::shared_ptr<AGamePanel> panel );
protected:
    virtual std::set<std::shared_ptr<CGameObject>> getItems() const override;
};

class CPlayerInteractionView:public CListView {
    Q_OBJECT
public:
    CPlayerInteractionView ( std::shared_ptr<AGamePanel> panel );
protected:
    virtual std::set<std::shared_ptr<CGameObject>> getItems() const override;
};

class CTradeItemsView : public CListView {
    Q_OBJECT
public:
    CTradeItemsView ( std::shared_ptr<AGamePanel> panel );
protected:
    virtual std::set<std::shared_ptr<CGameObject>> getItems() const override;
};

class CScrollObject : public CGameObject,public CClickAction {
public:
    CScrollObject ( std::shared_ptr<CListView> stats, bool isRight );
    void onClickAction ( std::shared_ptr<CGameObject> ) override;
private:
    std::weak_ptr<CListView> stats;
    bool isRight;
};

class CItemSlot : public CGameObject {
    Q_OBJECT
public:
    CItemSlot ( QString number, std::shared_ptr<AGamePanel> panel );
    QRectF boundingRect() const;
    void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
    static bool checkType ( QString slot, std::shared_ptr<CItem> item );
    void update();
    QString getNumber();
protected:
    void dragMoveEvent ( QGraphicsSceneDragDropEvent *event );
    void dropEvent ( QGraphicsSceneDragDropEvent *event );
private:
    QString number=QString::number ( -1 );
    QPixmap pixmap;
    std::weak_ptr<AGamePanel> panel;
};

