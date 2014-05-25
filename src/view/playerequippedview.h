#ifndef PLAYEREQUIPPEDVIEW_H
#define PLAYEREQUIPPEDVIEW_H

#include "itemslot.h"

#include <QGraphicsObject>

class Item;
class PlayerEquippedView : public QGraphicsObject
{
    Q_OBJECT
public:
    PlayerEquippedView(std::map<int, Item*>*equipped);
    QRectF boundingRect() const;
    void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget);
private:
    std::map<int, Item*>*equipped;
    std::list<ItemSlot*> itemSlots;
public slots:
    virtual void update();
};

#endif // PLAYEREQUIPPEDVIEW_H
