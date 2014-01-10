#include "mapscene.h"
#include "mapview.h"
#include <map/tile.h>
#include <QKeyEvent>
#include <map/map.h>
#include <QGraphicsSceneDragDropEvent>


MapView::MapView()
{
    showFullScreen();
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    setWindowState(Qt::WindowNoState);
    scene=new MapScene();
    setScene(scene);
    setAcceptDrops(true);
}

MapView::~MapView()
{
    delete scene;
}

void MapView::dragMoveEvent(QDragMoveEvent *event)
{
    QGraphicsView::dragMoveEvent(event);
    event->acceptProposedAction();
}


