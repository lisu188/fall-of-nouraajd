#ifndef ITEMSLOT_H
#define ITEMSLOT_H

#include <QGraphicsObject>

class ItemSlot : public QGraphicsObject
{
    Q_OBJECT
public:
    ItemSlot(int number);
    QRectF boundingRect() const;
    void paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *);
    static bool checkType(int slot, QWidget *widget);
protected:
    void dragMoveEvent(QGraphicsSceneDragDropEvent *event);
    void dropEvent(QGraphicsSceneDragDropEvent *event);
private:
    int number;
    QPixmap pixmap;
};

#endif // ITEMSLOT_H
