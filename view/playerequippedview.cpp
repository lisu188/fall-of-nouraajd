#include "playerequippedview.h"

#include <items/item.h>

PlayerEquippedView::PlayerEquippedView(std::map<int, Item *> *equipped):equipped(equipped)
{
    for(int i=0; i<equipped->size(); i++)
    {
        ItemSlot *slot=new ItemSlot(i,equipped);
        slot->setParentItem(this);
        slot->setPos(i%4*Map::getTileSize(),i/4*Map::getTileSize());
        itemSlots.push_back(slot);
    }
    update();
}

QRectF PlayerEquippedView::boundingRect() const
{
    return QRectF(0,0,4*Map::getTileSize(),2*Map::getTileSize());
}

void PlayerEquippedView::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
{
}

void PlayerEquippedView::update()
{
    for(std::list<ItemSlot*>::iterator it=itemSlots.begin();
            it!=itemSlots.end(); it++)
    {
        (*it)->update();
    }
}
