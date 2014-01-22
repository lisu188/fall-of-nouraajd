#include "gamescene.h"
#include "playerlistview.h"

#include <qpainter.h>
#include <QWidget>
#include <QDrag>
#include <QMimeData>

PlayerListView::PlayerListView(std::set<ListItem *> *listItems):items(listItems)
{
    this->setZValue(3);
    curPosition=0;
    right=new ScrollObject(this,true);
    left=new ScrollObject(this,false);
    x=4,y=4;
    pixmap.load(":/images/item.png");
    update();
}

void PlayerListView::update()
{
    if(curPosition<0) {
        curPosition=0;
    }
    if(items->size()-x*y<curPosition) {
        curPosition=items->size()-x*y;
    }
    QList<QGraphicsItem*> list=childItems();
    QList<QGraphicsItem *>::Iterator childIter;
    for(childIter=list.begin(); childIter!=list.end(); childIter++)
    {
        if(*childIter==right||*childIter==left) {
            continue;
        }
        (*childIter)->setParentItem(0);
        (*childIter)->setVisible(false);
    }
    std::set<ListItem *>::iterator itemIter;
    int i=0;
    for(itemIter=items->begin(); itemIter!=items->end(); i++,itemIter++)
    {
        ListItem *item=*itemIter;
        if(item->getMap()!=GameScene::getPlayer()->getMap())
        {
            item->setMap(GameScene::getPlayer()->getMap());
        }
        item->setVisible(false);
        item->setParentItem(0);
        int position=i-curPosition;
        if(position>=0&&position<x*y)
        {
            item->setParentItem(this);
            item->setNumber(position,x);
        }
    }
    right->setVisible(items->size()>x*y);
    right->setPos((x-1)*pixmap.size().width(),y*pixmap.size().height());
    left->setVisible(items->size()>x*y);
    left->setPos(0,y*pixmap.size().height());
}

Map *PlayerListView::getMap()
{
    if(items->size())
    {
        return (*items->begin())->getMap();
    }
    return 0;
}

void PlayerListView::setDraggable() {
    draggable=true;
}

QRectF PlayerListView::boundingRect() const
{
    return QRect(0,0,pixmap.size().width()*x,pixmap.size().height()*(items->size()>x*y?y+1:y));
}

void PlayerListView::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
{
    QList<QGraphicsItem*> list=childItems();
    QList<QGraphicsItem *>::Iterator childIter;
    for(childIter=list.begin(); childIter!=list.end(); childIter++)
    {
        if(*childIter==right||*childIter==left) {
            continue;
        }
        if(pixmap.size()!=(*childIter)->boundingRect().size()&&!(*childIter)->boundingRect().size().isEmpty())
            pixmap=pixmap.scaled((*childIter)->boundingRect().size().width(),
                                 (*childIter)->boundingRect().size().height()
                                 ,Qt::IgnoreAspectRatio,Qt::SmoothTransformation);
        painter->drawPixmap((*childIter)->pos(),pixmap);
    }
}

void PlayerListView::updatePosition(int i)
{
    curPosition+=i;
    update();
}

void PlayerListView::setXY(int x, int y)
{
    this->x=x;
    this->y=y;
}

void PlayerListView::dropEvent(QGraphicsSceneDragDropEvent *event)
{
    Item *item=(Item*)(event->source());
    event->acceptProposedAction();
    item->onUse(GameScene::getPlayer());
}


void PlayerListView::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    if(!draggable) {
        return;
    }
    QDrag *drag = new QDrag(this);
    QMimeData *mimeData = new QMimeData();
    drag->setMimeData(mimeData);
    drag->exec();
}
