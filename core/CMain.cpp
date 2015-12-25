#include "core/CGlobal.h"
#include "gui/CGui.h"
#include "core/CTypes.h"

static void messageHandler ( QtMsgType type, const QMessageLogContext &,
                             const QString &msg ) {
    static std::recursive_mutex mutex;
    std::unique_lock<std::recursive_mutex> lock ( mutex );
    QByteArray localMsg = msg.toLocal8Bit();
    switch ( type ) {
    case QtDebugMsg:
        fprintf ( stderr, "%s\n", localMsg.constData() );
        break;
    case QtInfoMsg:
        fprintf ( stderr, "%s\n", localMsg.constData() );
        break;
    case QtWarningMsg:
        fprintf ( stderr, "%s\n", localMsg.constData() );
        break;
    case QtCriticalMsg:
        fprintf ( stderr, "%s\n", localMsg.constData() );
        break;
    case QtFatalMsg:
        fprintf ( stderr, "%s\n", localMsg.constData() );
        abort();
    }
}

int main ( int argc, char *argv[] ) {
    qInstallMessageHandler ( messageHandler );
    CTypes::initialize();
    if ( argc == 2 ) {
        CResourcesProvider::getInstance()->save ( QString::fromUtf8 ( argv[1] ),
                CResourcesProvider::getInstance()->load ( QString::fromUtf8 ( argv[1] ) ) );
    } else {
        QApplication a ( argc, argv );
        CMainWindow window;
        window.show();
        return a.exec();
    }
    return 0;
}

