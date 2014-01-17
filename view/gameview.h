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
    void resize();
    FightView *getFightView() {
        return fightView;
    }
    void showFightView();
protected:
    void mouseDoubleClickEvent(QMouseEvent *e);
    void resizeEvent(QResizeEvent *event);
    virtual void wheelEvent(QWheelEvent *);
private:
    GameScene *scene;
    FightView *fightView;
    static bool init;
    QTimer timer;
    QGraphicsPixmapItem loading;
private slots:
    void start();
};

#endif // GAMEVIEW_H
