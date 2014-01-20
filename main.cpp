#include "view/gameview.h"

#include <QApplication>

#include <view/mapview.h>

#include <configuration/configurationprovider.h>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    QGraphicsView *view;
    bool editor=(*ConfigurationProvider::getConfig("config/init.json")).get("editor",false).asBool();
    if(editor) {
        view=new MapView();
    }
    else {
        view = new GameView();
    }
    int ret=a.exec();
    delete view;
    return ret;
}
