// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
// This observer is linked into the actual historical game; its original main remains active.
#include "recovery_smoke_config.h"
#include GAME_RECOVERY_SCENE_HEADER
#include GAME_RECOVERY_VIEW_HEADER
#include GAME_RECOVERY_MAP_HEADER
#include GAME_RECOVERY_PLAYER_HEADER

#include <QApplication>
#include <QElapsedTimer>
#include <QEvent>
#include <QFileInfo>
#include <QGraphicsView>
#include <QImage>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMainWindow>
#include <QPushButton>
#include <QSaveFile>
#include <QTimer>
#if GAME_RECOVERY_OPENGL
#include <QtOpenGL/QGLWidget>
#endif

namespace {
using RecoveryScene = GAME_RECOVERY_SCENE_TYPE;
using RecoveryView = GAME_RECOVERY_VIEW_TYPE;

class RecoveryStartupProbe : public QObject {
  public:
    explicit RecoveryStartupProbe(const QString &reportPath) : QObject(qApp), reportPath(reportPath) {
        elapsed.start();
        timer.setInterval(25);
        QObject::connect(&timer, &QTimer::timeout, this, [this]() { inspect(); });
        timer.start();
    }

  protected:
    bool eventFilter(QObject *watched, QEvent *event) override {
        if (view && watched == view->viewport() && event->type() == QEvent::Paint && awaitingFrame) {
            painted = true;
        }
        return false;
    }

  private:
    void finish(bool success, const QString &reason = QString(), const QImage &frame = QImage()) {
        timer.stop();
        QJsonObject checks;
        checks.insert("map", mapReady);
        checks.insert("player", playerReady);
        checks.insert("eventLoop", true);
        checks.insert("renderedFrame", success && painted);
        QJsonObject report;
        report.insert("schemaVersion", 1);
        report.insert("status", success ? "ready" : "failed");
        report.insert("checks", checks);
        report.insert("reason", reason);
        if (success) {
            const QString framePath = QFileInfo(reportPath).absolutePath() + "/startup.png";
            if (!frame.save(framePath, "PNG")) {
                finish(false, "Could not save the first rendered game frame");
                return;
            }
            QJsonObject frameInfo;
            frameInfo.insert("path", framePath);
            frameInfo.insert("width", frame.width());
            frameInfo.insert("height", frame.height());
            report.insert("frame", frameInfo);
        }
        QSaveFile output(reportPath);
        if (!output.open(QIODevice::WriteOnly) || output.write(QJsonDocument(report).toJson()) < 0 ||
            !output.commit()) {
            QCoreApplication::exit(42);
            return;
        }
        QCoreApplication::exit(success ? 0 : 41);
    }

    void inspect() {
        if (elapsed.elapsed() > 20000) {
            finish(false, "Map, player and rendered game frame did not become ready");
            return;
        }
        if (!view) {
            for (QWidget *widget : QApplication::topLevelWidgets()) {
                view = dynamic_cast<RecoveryView *>(widget);
                if (view) {
                    view->setWindowState(Qt::WindowNoState);
                    view->QWidget::resize(1280, 720);
                    view->show();
                    view->viewport()->installEventFilter(this);
                    break;
                }
                if (!menuActivated && dynamic_cast<QMainWindow *>(widget)) {
                    QPushButton *button = widget->findChild<QPushButton *>("pushButton");
                    if (button) {
                        menuActivated = true;
                        button->click();
                    }
                }
            }
        }
        if (!view || !view->isVisible()) {
            return;
        }
        RecoveryScene *scene = dynamic_cast<RecoveryScene *>(view->QGraphicsView::scene());
        if (!scene) {
            return;
        }
        auto *map = scene->GAME_RECOVERY_MAP_GETTER();
#if GAME_RECOVERY_STATIC_PLAYER
        auto *player = RecoveryScene::getPlayer();
#else
        auto *player = map ? map->getPlayer() : nullptr;
#endif
        playerReady = player && player->getHp() > 0 && player->getHpMax() > 0;
        if (!map || !playerReady) {
            return;
        }
#if GAME_RECOVERY_COORDS3
        mapReady = map->contains(player->getPosX(), player->getPosY(), player->getPosZ());
#else
        mapReady = map->contains(player->getPosX(), player->getPosY());
#endif
        if (!mapReady || scene->items().isEmpty()) {
            return;
        }
        if (!awaitingFrame) {
            awaitingFrame = true;
            view->viewport()->update();
            return;
        }
        if (!painted) {
            return;
        }
        QImage frame;
#if GAME_RECOVERY_OPENGL
        if (auto *gl = dynamic_cast<QGLWidget *>(view->viewport())) {
            frame = gl->grabFrameBuffer(true);
        } else {
            frame = view->viewport()->grab().toImage();
        }
#else
        frame = view->viewport()->grab().toImage();
#endif
        frame = frame.convertToFormat(QImage::Format_RGBA8888);
        if (frame.isNull() || frame.width() <= 0 || frame.height() <= 0) {
            finish(false, "The game viewport did not produce an image");
            return;
        }
        bool varied = false;
        const QRgb first = frame.pixel(0, 0);
        for (int y = 0; y < frame.height() && !varied; ++y) {
            for (int x = 0; x < frame.width(); ++x) {
                if (frame.pixel(x, y) != first) {
                    varied = true;
                    break;
                }
            }
        }
        if (!varied) {
            finish(false, "The first game frame is blank");
            return;
        }
        finish(true, QString(), frame);
    }

    QString reportPath;
    RecoveryView *view = nullptr;
    QTimer timer;
    QElapsedTimer elapsed;
    bool menuActivated = false;
    bool mapReady = false;
    bool playerReady = false;
    bool awaitingFrame = false;
    bool painted = false;
};

void installRecoveryStartupProbe() {
    const QByteArray path = qgetenv("GAME_RECOVERY_SMOKE_REPORT");
    if (!path.isEmpty()) {
        new RecoveryStartupProbe(QString::fromLocal8Bit(path));
    }
}
} // namespace

Q_COREAPP_STARTUP_FUNCTION(installRecoveryStartupProbe)
