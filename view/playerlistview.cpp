#include "gamescene.h"
#include "playerlistview.h"

#include <qpainter.h>

PlayerListView::PlayerListView(std::list<ListItem *> *listItems):items(listItems)
{
    this->setZValue(3);
    curPosition=0;
    right=new ScrollObject(this,true);
    left=new ScrollObject(this,false);
    x=4,y=4;
}

void PlayerListView::update()
{
    if(curPosition<0)curPosition=0;
    if(items->size()-x*y<curPosition)curPosition=items->size()-x*y;

    QList<QGraphicsItem*> list=childItems();
    QList<QGraphicsItem *>::Iterator chilIter;
    for(chilIter=list.begin(); chilIter!=list.end(); chilIter++)
    {
        (*chilIter)->setParentItem(0);
        (*chilIter)->setVisible(false);
    }

    std::list<ListItem *>::iterator itemIter;
    int i=0;
    for(itemIter=items->begin(); itemIter!=items->end(); i++,itemIter++)
    {
        (*itemIter)->setVisible(false);
        (*itemIter)->setParentItem(0);

        int position=i-curPosition;

        if(position>=0&&position<x*y)
        {
            (*itemIter)->setParentItem(this);
            (*itemIter)->setNumber(position,x);
        }

    }

    right->setVisible(items->size()>x*y);
    left->setVisible(items->size()>x*y);

    if(GameScene::getView())
    {
        GameScene::getPlayer()->update();
    }
}

QRectF PlayerListView::boundingRect() const
{
    return childrenBoundingRect();
}

void PlayerListView::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
{

}

void PlayerListView::updatePosition(int i)
{
    curPosition+=i;
    update();
}
