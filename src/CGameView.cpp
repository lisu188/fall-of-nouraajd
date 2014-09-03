#include "CCreature.h"
#include "CGameView.h"
#include <src/CInteraction.h>
#include <QDebug>
#include <vector>
#include <initializer_list>
#include <QPainter>
#include <QMouseEvent>
#include <src/CPlayerView.h>


bool CGameView::init = false;

void CGameView::start() {
    scene->startGame(mapName, playerType);
    charView->setUpPanel(this);
    fightView->setUpPanel(this);
    playerStatsView.setPlayer(scene->getPlayer());
    playerStatsView.update();
    scene->removeItem(&loading);
    init = true;
}

CGameView::CGameView(std::string mapName, std::string playerType) : mapName(mapName), playerType(playerType) {
    setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
    /*
    view.setViewport(new QGLWidget(
             QGLFormat(QGL::SampleBuffers)));
    view.setViewportUpdateMode(
             QGraphicsView::FullViewportUpdate);
    */
    scene = new CGameScene();
    setScene(scene);
    QPixmap pixmap(":/images/loading.png");
    loading.setPixmap(pixmap.scaled(this->width(), this->height(), Qt::IgnoreAspectRatio, Qt::SmoothTransformation));
    scene->addItem(&loading);

    fightView = new CFightPanel();
    charView = new CCharPanel();

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

CGameView::~CGameView() {
    delete scene;
}

CFightPanel *CGameView::getFightView() { return fightView; }

CCharPanel *CGameView::getCharView() { return charView; }

void CGameView::showCharView() {
    charView->showPanel(this);
}

void CGameView::showFightView() {
    fightView->showPanel(this);
}

void CGameView::mouseDoubleClickEvent(QMouseEvent *e) {
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

void CGameView::resizeEvent(QResizeEvent *event) {
    if (event) {
        QWidget::resizeEvent(event);
    }
    backpack.move((width() - backpack.width()) / 2, 0);
    playerStatsView.move(0, 0);
    if (init) {
        int size = scene->getMap()->getTileSize();
        CPlayer *player = scene->getPlayer();
        centerOn(player->getPosX() * size + size / 2, player->getPosY() * size + size / 2);
    }
}

void CGameView::wheelEvent(QWheelEvent *) {}

void CGameView::dragMoveEvent(QDragMoveEvent *e) {
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


void CGameView::show() {
    showFullScreen();
}

CGameScene *CGameView::getScene() const { return scene; }

void CGameView::setScene(CGameScene *value) {
    scene = value;
    QGraphicsView::setScene(value);
}
