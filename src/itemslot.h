#ifndef ITEMSLOT_H
#define ITEMSLOT_H

#include <QGraphicsObject>

#include <src/item.h>

class ItemSlot : public QGraphicsObject {
  Q_OBJECT
public:
  ItemSlot(int number, std::map<int, Item *> *equipped);
  QRectF boundingRect() const;
  void paint(QPainter *painter, const QStyleOptionGraphicsItem *, QWidget *);
  static bool checkType(int slot, QWidget *widget);
  void update();
  int getNumber() { return number; }

protected:
  void dragMoveEvent(QGraphicsSceneDragDropEvent *event);
  void dropEvent(QGraphicsSceneDragDropEvent *event);

private:
  int number;
  QPixmap pixmap;
  std::map<int, Item *> *equipped;
};

#endif // ITEMSLOT_H
