#include "gameview.h"
#include <QDebug>
#include <QPainter>
#include <QMouseEvent>
#include <QDateTime>
#include <src/playerlistview.h>

bool GameView::init=false;

void GameView::start()
{

        scene->startGame("maps/map.tmx");
        scene->removeItem(&loading);
        Player *player = scene->getPlayer();
        playerInventoryView = new PlayerListView((std::set<ListItem *, Comparer> *)player->getInventory());
        playerSkillsView = new PlayerListView((std::set<ListItem *, Comparer> *)player->getActions());
        playerEquippedView = new PlayerEquippedView(player->getEquipped());
        playerInventoryView->setParentItem(charView);
        playerEquippedView->setParentItem(charView);
        scene->addItem(playerSkillsView);
        connect(player, SIGNAL(inventoryChanged()), playerInventoryView, SLOT(update()));
        connect(player, SIGNAL(skillsChanged()), playerSkillsView, SLOT(update()));
        connect(player, SIGNAL(equippedChanged()), playerEquippedView, SLOT(update()));
        playerStatsView.setPlayer(player);
        init=true;

}

GameView::GameView()
{
    playerInventoryView = 0;
    playerSkillsView = 0;
    playerEquippedView = 0;
    playerStatsView.setParent(this);
    backpack.setParent(this);
    backpack.move(260, 0);
    connect(&backpack, SIGNAL(clicked()), this, SLOT(showCharView()));
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
    QPixmap pixmap(":/images/loading.png");
    loading.setPixmap(pixmap.scaled(this->width(),this->height(),
                                    Qt::IgnoreAspectRatio,Qt::SmoothTransformation));
    scene->addItem(&loading);

    fightView=new FightView();
    charView=new CharView();

    scene->addItem(fightView);
    scene->addItem(charView);

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

CharView *GameView::getCharView(){return charView;}

void GameView::showCharView()
{
    if(!charView->isVisible()){

    charView->setVisible(true);
    charView->setPos(mapToScene(this->width()/2-charView->boundingRect().width()/2,this->height()/2
                                 -charView->boundingRect().height()/2));
    playerInventoryView->setPos(0,0);
    playerEquippedView->setPos(this->getCharView()->boundingRect().width()-
                                                      playerEquippedView->boundingRect().width(),0);
    charView->update();
    }
    else
    {
        charView->setVisible(false);
    }
}

void GameView::showFightView()
{
    std::list<Creature *> *fightlist=scene->getPlayer()->getFightList();
    FightView::selected=fightlist->front();
    for(std::list<Creature*>::iterator it=fightlist->begin(); it!=fightlist->end(); it++)
    {
        qDebug()<<(*it)->typeName.c_str()<<"attacked"<<scene->getPlayer()->typeName.c_str();
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
        int size=scene->getMap()->getTileSize();
        Player *player=scene->getPlayer();
        centerOn(player->getPosX()*size+size/2,player->getPosY()*size+size/2);
        player->updateViews();
    }
}

void GameView::wheelEvent(QWheelEvent *)
{
}


void GameView::dragMoveEvent(QDragMoveEvent *e)
{
    QGraphicsView::dragMoveEvent(e);
    repaint();
}


BackPackObject::BackPackObject() : pixmap(":/images/backpack.png") {
    setFixedSize(50, 50);
}
void BackPackObject::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.drawPixmap(rect(), pixmap);
}
void BackPackObject::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton) {
        Q_EMIT clicked();
        event->accept();
    } else {
        QWidget::mousePressEvent(event);
    }
}
