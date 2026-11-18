// Copyright (C) 2026 Andrzej Lis
// SPDX-License-Identifier: GPL-3.0-or-later
// This observer is linked into the actual historical game; its original main remains active.
#include "recovery_smoke_config.h"
#include GAME_RECOVERY_SCENE_HEADER
#include GAME_RECOVERY_VIEW_HEADER
#include GAME_RECOVERY_MAP_HEADER
#if !GAME_RECOVERY_EDITOR
#include GAME_RECOVERY_PLAYER_HEADER
#endif

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
#include <QThreadPool>
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
#if GAME_RECOVERY_EDITOR
        checks.insert("editor", editorReady);
#else
        checks.insert("player", playerReady);
#endif
        checks.insert("eventLoop", true);
        checks.insert("renderedFrame", success && painted);
        QJsonObject report;
        report.insert("schemaVersion", 1);
#if GAME_RECOVERY_EDITOR
        report.insert("mode", "editor");
        report.insert("validationBoundary", "Authored editor startup; gameplay and player are unverified");
#else
        report.insert("mode", "game");
#endif
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

    // Background loading may legitimately take longer than the readiness deadline; the
    // verifier passes how long it will wait (its watchdog minus a margin).
    static qint64 loadDeadlineMs() {
        bool ok = false;
        const qint64 value = qgetenv("GAME_RECOVERY_LOAD_DEADLINE_MS").toLongLong(&ok);
        return ok && value > 20000 ? value : 50000;
    }

    void inspect() {
        // Once genuine background work has been seen (even while the game keeps its view
        // hidden), the longer loading deadline applies instead of the readiness deadline.
        if (QThreadPool::globalInstance()->activeThreadCount() > 0) {
            backgroundBusy = true;
        }
        if (elapsed.elapsed() > (backgroundBusy ? loadDeadlineMs() : 20000)) {
#if GAME_RECOVERY_EDITOR
            finish(false, "Editor map and rendered frame did not become ready");
#else
            finish(false, "Map, player and rendered game frame did not become ready");
#endif
            return;
        }
        if (!view) {
            for (QWidget *widget : QApplication::topLevelWidgets()) {
                view = dynamic_cast<RecoveryView *>(widget);
                // A game that shows its view only after background loading (#226 LoadGameTask)
                // must not be shown early; a still-hidden view is shown once the game is idle.
                if (view && !view->isVisible() &&
                    (elapsed.elapsed() < 5000 || QThreadPool::globalInstance()->activeThreadCount() > 0)) {
                    view = nullptr;
                    continue;
                }
                if (view) {
                    view->setWindowState(Qt::WindowNoState);
                    view->QWidget::resize(1280, 720);
                    view->show();
                    view->viewport()->installEventFilter(this);
                    break;
                }
#if !GAME_RECOVERY_EDITOR
                if (!menuActivated && dynamic_cast<QMainWindow *>(widget)) {
                    QPushButton *button = widget->findChild<QPushButton *>("pushButton");
                    if (button) {
                        menuActivated = true;
                        button->click();
                    }
                }
#endif
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
#if GAME_RECOVERY_EDITOR
        editorReady = map && map->getScene() == scene && map->getTileSize() > 0;
        mapReady = editorReady && !map->empty();
#else
#if GAME_RECOVERY_STATIC_PLAYER
        auto *player = RecoveryScene::getPlayer();
#elif defined(GAME_RECOVERY_SCENE_PLAYER) && GAME_RECOVERY_SCENE_PLAYER
        auto *player = scene->getPlayer();
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
        // Historical background loading (for example LoadGameTask from #226) blocks on the
        // event loop; exiting before it settles would deadlock the original thread pool.
        if (QThreadPool::globalInstance()->activeThreadCount() > 0) {
            backgroundBusy = true;
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
    bool backgroundBusy = false;
    bool mapReady = false;
#if GAME_RECOVERY_EDITOR
    bool editorReady = false;
#else
    bool playerReady = false;
#endif
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
