#ifndef PLAYEREQUIPPEDVIEW_H
#define PLAYEREQUIPPEDVIEW_H

#include <QGraphicsObject>

class Item;
class PlayerEquippedView : public QGraphicsObject
{
    Q_OBJECT
public:
    PlayerEquippedView(std::map<int,Item*>*equipped);
private:
    std::map<int,Item*>*equipped;
};

#endif // PLAYEREQUIPPEDVIEW_H
