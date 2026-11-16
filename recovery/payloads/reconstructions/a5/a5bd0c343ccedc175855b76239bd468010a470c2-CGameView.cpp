#include "CCreature.h"
#include "CGameView.h"
#include "CMap.h"
#include "CLootProvider.h"
#include "CPlayerView.h"
#include "Util.h"
#include <QApplication>
#include <QBitmap>
#include <QDateTime>
#include <QDebug>
#include <QDesktopWidget>
#include <QMouseEvent>
#include <QPainter>
#include <QResizeEvent>
#include <QThreadPool>
#include <QtOpenGL/QGLWidget>

bool CGameView::init = false;

void CGameView::start() {
  scene->startGame(mapName, playerType);
  scene->removeItem(&loading);
  CPlayer *player = scene->getPlayer();
  playerStatsView.show();
  playerStatsView.setPlayer(player);
  fightView->setUpPanel(this);
  charView->setUpPanel(this);
  init = true;
}

void CGameView::show() { showNormal(); }

CGameView::CGameView(QString mapName, QString playerType) {
  this->mapName = mapName;
  this->playerType = playerType;
  setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
  setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
  setViewportUpdateMode(QGraphicsView::BoundingRectViewportUpdate);
  setViewport(new QGLWidget(QGLFormat(QGL::SampleBuffers)));
  setViewportUpdateMode(QGraphicsView::FullViewportUpdate);
  scene = new CGameScene();
  setScene(scene);
  QPixmap pixmap("images/loading.png");
  loading.setPixmap(pixmap.scaled(this->width(), this->height(),
                                  Qt::IgnoreAspectRatio,
                                  Qt::SmoothTransformation));
  scene->addItem(&loading);
  timer.setSingleShot(true);
  timer.setInterval(250);
  connect(&timer, SIGNAL(timeout()), this, SLOT(start()));
  playerStatsView.setParent(this);
  fightView = new CFightPanel();
  charView = new CCharPanel();
  scene->addItem(fightView);
  scene->addItem(charView);
  backpack.setParent(this);
  backpack.show();
  connect(&backpack, SIGNAL(clicked()), this, SLOT(showCharView()));
  timer.start();
}

CGameView::~CGameView() {
  delete scene->getMap();
  delete scene;
}

CFightPanel *CGameView::getFightView() { return fightView; }
CCharPanel *CGameView::getCharView() { return charView; }
void CGameView::showCharView() {
  if (init) {
    charView->showPanel(this);
  }
}
void CGameView::showFightView() {
  if (!init || scene->getPlayer()->getFightList()->empty()) {
    return;
  }
  CFightPanel::selected = scene->getPlayer()->getFightList()->front();
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
    playerStatsView.move(0, 0);
    backpack.move(width() - backpack.width(), 0);
  }
  if (init) {
    CPlayer *player = scene->getPlayer();
    centerOn(player);
  }
}

void CGameView::wheelEvent(QWheelEvent *) {}

void CGameView::dragMoveEvent(QDragMoveEvent *e) {
  QGraphicsView::dragMoveEvent(e);
  repaint();
}

CGameScene *CGameView::getScene() const { return scene; }

void CGameView::setScene(CGameScene *value) {
  QGraphicsView::setScene(value);
  scene = value;
}

BackPackObject::BackPackObject() : pixmap("images/backpack.png") {
  setFixedSize(pixmap.size());
  setAttribute(Qt::WA_TranslucentBackground);
}
void BackPackObject::mousePressEvent(QMouseEvent *event) {
  if (event->button() == Qt::LeftButton) {
    Q_EMIT clicked();
    event->accept();
  } else {
    QWidget::mousePressEvent(event);
  }
}
void BackPackObject::paintEvent(QPaintEvent *) {
  QPainter painter(this);
  painter.drawPixmap(0, 0, pixmap);
}
