#include "view/gameview.h"

#include <QApplication>
#include <QGraphicsScene>
#include <QGraphicsView>
#include <QPropertyAnimation>
#include <QGraphicsWidget>
#include <QGraphicsItem>

#include <view/gamescene.h>
#include <map/tiles/grasstile.h>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    GameView view;
    return a.exec();
}


