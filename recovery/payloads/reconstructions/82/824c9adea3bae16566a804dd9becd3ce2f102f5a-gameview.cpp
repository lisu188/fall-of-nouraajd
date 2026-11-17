#include "gameview.h"
#include <QDebug>
#include <QPainter>
#include <QMouseEvent>
#include <view/playerlistview.h>

bool GameView::init = false;

void GameView::start() {

    scene->startGame();
    Player *player = GameScene::getPlayer();
    playerStatsView.setPlayer(player);
    playerStatsView.update();

    // The player's lists are shown by the view and refreshed by the creature's signals.
    playerInventoryView = new PlayerListView((std::set<ListItem *> *)player->getInventory());
    playerSkillsView = new PlayerListView((std::set<ListItem *> *)player->getActions());
    playerEquippedView = new PlayerListView((std::set<ListItem *> *)player->getEquipped());
    playerInventoryView->setParentItem(charView);
    playerEquippedView->setParentItem(charView);
    scene->addItem(playerSkillsView);
    connect(player, SIGNAL(inventoryChanged()), playerInventoryView, SLOT(update()));
    connect(player, SIGNAL(skillsChanged()), playerSkillsView, SLOT(update()));
    connect(player, SIGNAL(equippedChanged()), playerEquippedView, SLOT(update()));
    scene->removeItem(&loading);
    init = true;
}

GameView::GameView() {
    showFullScreen();
    setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    /*
    view.setViewport(new QGLWidget(
             QGLFormat(QGL::SampleBuffers)));
    view.setViewportUpdateMode(
             QGraphicsView::FullViewportUpdate);
    */
    scene = new GameScene();
    setScene(scene);
    QPixmap pixmap(":/images/loading.png");
    loading.setPixmap(pixmap.scaled(this->width(), this->height(), Qt::IgnoreAspectRatio, Qt::SmoothTransformation));
    scene->addItem(&loading);

    fightView = new FightView();
    charView = new CharView();

    scene->addItem(fightView);
    scene->addItem(charView);

    backpack.setParent(this);
    playerStatsView.setParent(this);
    connect(&backpack, SIGNAL(clicked()), this, SLOT(showCharView()));
    backpack.move((width() - backpack.width()) / 2, 0);
    playerStatsView.move(0, 0);
    backpack.show();
    playerStatsView.show();

    timer.setSingleShot(true);
    timer.setInterval(50);
    connect(&timer, SIGNAL(timeout()), this, SLOT(start()));
    timer.start();
}

GameView::~GameView() { delete scene; }

FightView *GameView::getFightView() { return fightView; }

CharView *GameView::getCharView() { return charView; }

void GameView::showCharView() {
    if (!charView->isVisible()) {

        charView->setVisible(true);
        charView->setPos(mapToScene(this->width() / 2 - charView->boundingRect().width() / 2,
                                    this->height() / 2 - charView->boundingRect().height() / 2));
        playerInventoryView->setPos(0, 0);
        playerEquippedView->setPos(charView->boundingRect().width() - playerEquippedView->boundingRect().width(), 0);
        charView->update();
    } else {
        charView->setVisible(false);
    }
}

void GameView::showFightView() {
    std::list<Creature *> *fightlist = GameScene::getPlayer()->getFightList();
    FightView::selected = fightlist->front();
    for (std::list<Creature *>::iterator it = fightlist->begin(); it != fightlist->end(); it++) {
        qDebug() << (*it)->className.c_str() << "attacked" << GameScene::getPlayer()->className.c_str();
    }
    qDebug() << "";
    fightView->setVisible(true);
    fightView->setPos(mapToScene(this->width() / 2 - fightView->boundingRect().width() / 2,
                                 this->height() / 2 - fightView->boundingRect().height() / 2));
    fightView->update();
}

void GameView::mouseDoubleClickEvent(QMouseEvent *e) {
    QWidget::mouseDoubleClickEvent(e);
    if (e->button() == Qt::MouseButton::LeftButton || !init) {
        return;
    }
    if (isFullScreen()) {
        this->setWindowState(Qt::WindowNoState);
    } else {
        this->setWindowState(Qt::WindowFullScreen);
    }
}

void GameView::resizeEvent(QResizeEvent *event) {
    if (event) {
        QWidget::resizeEvent(event);
    }
    if (init) {
        int size = GameScene::getGame()->getMap()->getTileSize();
        Player *player = GameScene::getPlayer();
        centerOn(player->getPosX() * size + size / 2, player->getPosY() * size + size / 2);
        playerSkillsView->setPos(mapToScene(width() - playerSkillsView->boundingRect().width(),
                                            height() - playerSkillsView->boundingRect().height()));
    }
}

void GameView::wheelEvent(QWheelEvent *) {}

void GameView::dragMoveEvent(QDragMoveEvent *e) {
    QGraphicsView::dragMoveEvent(e);
    repaint();
}

BackPackObject::BackPackObject() : pixmap(":/images/backpack.png") {
    setFixedSize(pixmap.size());
    setAttribute(Qt::WA_TranslucentBackground);
}

void BackPackObject::mousePressEvent(QMouseEvent *event) {
    if (event && event->button() == Qt::LeftButton) {
        emit clicked();
        event->accept();
        return;
    }
    QWidget::mousePressEvent(event);
}

void BackPackObject::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.drawPixmap(0, 0, pixmap);
}
