#include "mapscene.h"
#include "mapview.h"
#include <map/tile.h>
#include <QKeyEvent>


MapView::MapView()
{
    showFullScreen();
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    setWindowState(Qt::WindowNoState);
    scene=new MapScene();
    setScene(scene);
}

MapView::~MapView()
{
    delete scene;
}
