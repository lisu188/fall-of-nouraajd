#include "gameview.h"
#include <src/interaction.h>
#include <QDebug>
#include <vector>
#include <initializer_list>
#include <QPainter>
#include <QMouseEvent>
#include <src/playerlistview.h>


bool GameView::init = false;

void GameView::start() {
    scene->startGame(mapName, playerType);
    charView->setUpPanel(this);
    fightView->setUpPanel(this);
    playerStatsView.setPlayer(scene->getPlayer());
    playerStatsView.update();
    scene->removeItem(&loading);
    init = true;
}

GameView::GameView(std::string mapName, std::string playerType) : mapName(mapName), playerType(playerType) {
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

    fightView = new FightPanel();
    charView = new CharPanel();

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

GameView::~GameView() {
    delete scene;
}

FightPanel *GameView::getFightView() { return fightView; }

CharPanel *GameView::getCharView() { return charView; }

void GameView::showCharView() {
    charView->showPanel(this);
}

void GameView::showFightView() {
    fightView->showPanel(this);
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
    backpack.move((width() - backpack.width()) / 2, 0);
    playerStatsView.move(0, 0);
    if (init) {
        int size = scene->getMap()->getTileSize();
        Player *player = scene->getPlayer();
        centerOn(player->getPosX() * size + size / 2, player->getPosY() * size + size / 2);
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
        Q_EMIT clicked();
        event->accept();
        return;
    }
    QWidget::mousePressEvent(event);
}

void BackPackObject::paintEvent(QPaintEvent *) {
    QPainter painter(this);
    painter.drawPixmap(0, 0, pixmap);
}


void GameView::show() {
    showFullScreen();
}

GameScene *GameView::getScene() const { return scene; }

void GameView::setScene(GameScene *value) {
    scene = value;
    QGraphicsView::setScene(value);
}
