#ifndef GAMEVIEW_H
#define GAMEVIEW_H

#include "gamescene.h"

#include <QGraphicsView>
#include <QThread>
#include <view/fightview.h>

class GameView : public QGraphicsView
{
    Q_OBJECT
public:
    GameView();
    ~GameView();
    FightView *getFightView();
    void showFightView();
protected:
    void mouseDoubleClickEvent(QMouseEvent *e);
    void resizeEvent(QResizeEvent *event);
    virtual void wheelEvent(QWheelEvent *);
    virtual void dragMoveEvent(QDragMoveEvent *e);
private:
    GameScene *scene;
    FightView *fightView;
    CharView *charView;
    static bool init;
    QTimer timer;
    QGraphicsPixmapItem loading;
private slots:
    void start();
};

#endif // GAMEVIEW_H
