#include "gameview.h"
#include <QDebug>

bool GameView::init=false;

void GameView::start()
{
    if(!init)
    {
        scene->startGame();
        scene->removeItem(&loading);
        init=true;
        timer.start();
    }
    else
    {
        setWindowState(Qt::WindowFullScreen);
    }
}

GameView::GameView()
{
    showFullScreen();
    setWindowState(Qt::WindowNoState);
    setHorizontalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
    setVerticalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    /*
    view.setViewport(new QGLWidget(
             QGLFormat(QGL::SampleBuffers)));
    view.setViewportUpdateMode(
             QGraphicsView::FullViewportUpdate);
    */
    scene=new GameScene();
    setScene(scene);
    QPixmap pixmap(":/images/loading.png");
    loading.setPixmap(pixmap.scaled(this->width(),this->height(),
                                    Qt::IgnoreAspectRatio,Qt::SmoothTransformation));
    scene->addItem(&loading);
    fightView=new FightView();
    scene->addItem(fightView);
    timer.setSingleShot(true);
    timer.setInterval(50);
    connect(&timer, SIGNAL(timeout()), this, SLOT(start()));
    timer.start();
}

GameView::~GameView()
{
    delete scene;
}

FightView *GameView::getFightView() {
    return fightView;
}

void GameView::showFightView()
{
    std::list<Creature *> *fightlist=GameScene::getPlayer()->getFightList();
    FightView::selected=fightlist->front();
    for(std::list<Creature*>::iterator it=fightlist->begin(); it!=fightlist->end(); it++)
    {
        qDebug()<<(*it)->className.c_str()<<"attacked"<<GameScene::getPlayer()->className.c_str();
    }
    qDebug()<<"";
    fightView->setVisible(true);
    fightView->setPos(mapToScene(this->width()/2-fightView->boundingRect().width()/2,this->height()/2
                                 -fightView->boundingRect().height()/2));
    fightView->update();
}

void GameView::mouseDoubleClickEvent(QMouseEvent *e) {
    QWidget::mouseDoubleClickEvent(e);
    if(e->button()==Qt::MouseButton::LeftButton||!init) {
        return;
    }
    if(isFullScreen()) {
        this->setWindowState(Qt::WindowNoState);
    } else {
        this->setWindowState(Qt::WindowFullScreen);
    }
}

void GameView::resizeEvent( QResizeEvent * event)
{
    if(event) {
        QWidget::resizeEvent(event);
    }
    if(init)
    {
        int size=GameScene::getGame()->getMap()->getTileSize();
        Player *player=GameScene::getPlayer();
        centerOn(player->getPosX()*size+size/2,player->getPosY()*size+size/2);
        player->update();
    }
}

void GameView::wheelEvent(QWheelEvent *)
{
}
