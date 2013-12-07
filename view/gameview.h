#ifndef GAMEVIEW_H
#define GAMEVIEW_H

#include "gamescene.h"

#include <QGraphicsView>
#include <view/fightview.h>

class GameView : public QGraphicsView
{

public:
    explicit GameView();
    ~GameView();
    void resize();
    FightView *getFightView() {
        return fightView;
    }
    void showFightView();
protected:
    void mouseDoubleClickEvent(QMouseEvent *e);
    void resizeEvent(QResizeEvent *event);
    virtual void wheelEvent(QWheelEvent *event);
private:
    GameScene *scene;
    FightView *fightView;
    static bool init;
};

#endif // GAMEVIEW_H
