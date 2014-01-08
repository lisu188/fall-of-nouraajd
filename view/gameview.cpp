#include "gameview.h"
#include <QDebug>

bool GameView::init=false;

void GameView::start()
{
    scene->startGame();
    scene->removeItem(&loading);
    init=true;
    showFullScreen();
    resize();
}

GameView::GameView()
{
    showFullScreen();
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
    QPixmap pixmap("images/loading.jpg");
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

void GameView::resize()
{
    resizeEvent(0);
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
    QWidget::resizeEvent(event);
    if(init)
    {
        int size=Tile::size;
        Player *player=GameScene::getPlayer();
        centerOn(player->getPosX()*size+size/2,player->getPosY()*size+size/2);
        player->update();
        if(event)
        {
            int sizex=(event->size().width()/Tile::size+1);
            int sizey=(event->size().height()/Tile::size+1);
        }
    }
}

void GameView::wheelEvent(QWheelEvent *event)
{
    event->setAccepted(true);
}
