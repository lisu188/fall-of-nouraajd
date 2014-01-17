#include "gamescene.h"
#include "playerlistview.h"

#include <qpainter.h>
#include <QWidget>
#include <QDrag>
#include <QMimeData>

PlayerListView::PlayerListView(std::list<ListItem *> *listItems):items(listItems)
{
    this->setZValue(3);
    curPosition=0;
    right=new ScrollObject(this,true);
    left=new ScrollObject(this,false);
    x=4,y=4;
    pixmap=new QPixmap(":/images/item.jpg");
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
        ListItem *item=*itemIter;
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
    left->setVisible(items->size()>x*y);
    if(GameScene::getView()&&GameScene::getPlayer())
    {
        GameScene::getPlayer()->update();
    }
}

QRectF PlayerListView::boundingRect() const
{
    QRectF rect=childrenBoundingRect();
    if(rect.width()<50||rect.height()<50) {
        return QRectF(0,0,50,50);
    }
    return rect;
}

void PlayerListView::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
{
    QList<QGraphicsItem*> list=childItems();
    QList<QGraphicsItem *>::Iterator chilIter;
    for(chilIter=list.begin(); chilIter!=list.end(); chilIter++)
    {
        if(pixmap->size()!=(*chilIter)->boundingRect().size()&&!(*chilIter)->boundingRect().size().isEmpty())
            (*pixmap)=pixmap->scaled((*chilIter)->boundingRect().size().width(),
                                 (*chilIter)->boundingRect().size().height()
                                 ,Qt::IgnoreAspectRatio,Qt::SmoothTransformation);
        painter->drawPixmap((*chilIter)->pos(),*pixmap);
    }
}

void PlayerListView::updatePosition(int i)
{
    curPosition+=i;
    update();
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
