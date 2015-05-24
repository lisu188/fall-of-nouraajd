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
    CPlayerView ( AGamePanel* panel );
protected:
    virtual void dropEvent ( QGraphicsSceneDragDropEvent *event );
    AGamePanel *panel=0;
};

class CPlayerEquippedView : public CPlayerView {
    Q_OBJECT
public:
    CPlayerEquippedView ( AGamePanel *panel );
    QRectF boundingRect() const;
    void paint ( QPainter *, const QStyleOptionGraphicsItem *, QWidget * );
    void update();
private:
    std::list<CItemSlot *> itemSlots;
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
    CListView ( AGamePanel *panel );
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
    CScrollObject *right, *left;
    QPixmap pixmap;
};

class CPlayerInventoryView:public CListView {
    Q_OBJECT
public:
    CPlayerInventoryView ( AGamePanel *panel );
protected:
    virtual std::set<std::shared_ptr<CGameObject>> getItems() const override;
};

class CPlayerIteractionView:public CListView {
    Q_OBJECT
public:
    CPlayerIteractionView ( AGamePanel *panel );
protected:
    virtual std::set<std::shared_ptr<CGameObject>> getItems() const override;
};

class CTradeItemsView : public CListView {
    Q_OBJECT
public:
    CTradeItemsView ( AGamePanel *panel  );
protected:
    virtual std::set<std::shared_ptr<CGameObject>> getItems() const override;
};

class CScrollObject : public CGameObject,public CClickAction {
public:
    CScrollObject ( CListView *stats, bool isRight );
    void setVisible ( bool visible );
    void onClickAction ( std::shared_ptr<CGameObject> ) override;
private:
    bool isRight;
    CListView *stats;
};

class CItemSlot : public CGameObject {
    Q_OBJECT
public:
    CItemSlot ( int number, AGamePanel *panel );
    QRectF boundingRect() const;
    void paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * );
    static bool checkType ( int slot, std::shared_ptr<CItem> item );
    void update();
    int getNumber();

protected:
    void dragMoveEvent ( QGraphicsSceneDragDropEvent *event );
    void dropEvent ( QGraphicsSceneDragDropEvent *event );

private:
    int number=-1;
    QPixmap pixmap;
    AGamePanel * panel=0;
};

