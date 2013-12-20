#include "view/gameview.h"

#include <QApplication>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    GameView view;
    return a.exec();
}


