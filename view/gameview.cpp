#include "gameview.h"

bool GameView::init=false;

GameView::GameView()
{
    showFullScreen();
    //this->setWindowState(Qt::WindowNoState);
    setHorizontalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
    setVerticalScrollBarPolicy ( Qt::ScrollBarAlwaysOff );
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    /*
    view.setViewport(new QGLWidget(
             QGLFormat(QGL::SampleBuffers)));
    view.setViewportUpdateMode(
             QGraphicsView::FullViewportUpdate);
    */
    init=true;
    scene=new GameScene();
    setScene(scene);
    resize();
    fightView=new FightView();
    scene->addItem(fightView);
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
    FightView::selected=GameScene::getPlayer()->getFightList()->front();
    fightView->setVisible(true);
    fightView->setPos(mapToScene(this->width()/2-fightView->boundingRect().width()/2,this->height()/2
                                 -fightView->boundingRect().height()/2));
    fightView->update();
}

void GameView::mouseDoubleClickEvent(QMouseEvent *e) {
    QWidget::mouseDoubleClickEvent(e);
    if(e->button()==Qt::MouseButton::LeftButton) {
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
            GameScene::getGame()->ensureSize(sizex,sizey);
        }
    }
}

void GameView::wheelEvent(QWheelEvent *event)
{
    event->setAccepted(true);
}
