#include "view/gameview.h"

#include <QApplication>

#include <view/mapview.h>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    GameView gameview;
    MapView mapview;
    return a.exec();
}


