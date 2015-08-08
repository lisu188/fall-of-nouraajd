#include "CGlobal.h"
#include "gui/CGui.h"


static void messageHandler ( QtMsgType type, const QMessageLogContext &context,
                             const QString &msg ) {
    static std::mutex mutex;
    std::unique_lock<std::mutex> lock ( mutex );
    QByteArray localMsg = msg.toLocal8Bit();
    switch ( type ) {
    case QtDebugMsg:
        fprintf ( stderr, "%s\n", localMsg.constData() );
        break;
    case QtWarningMsg:
        fprintf ( stderr, "Warning: %s (%s:%u, %s)\n", localMsg.constData(),
                  context.file, context.line, context.function );
        break;
    case QtCriticalMsg:
        fprintf ( stderr, "Critical: %s (%s:%u, %s)\n", localMsg.constData(),
                  context.file, context.line, context.function );
        break;
    case QtFatalMsg:
        fprintf ( stderr, "Fatal: %s (%s:%u, %s)\n", localMsg.constData(),
                  context.file, context.line, context.function );
        abort();
    }
}

static class init {
public:
    init() {
        qInstallMessageHandler ( messageHandler );
        std::set_terminate ( [] (  )-> void {
            PyErr_Print();
            abort();
        } );
    }
} a;


int main ( int argc, char *argv[] ) {
    if ( argc==2 ) {
        CResourcesProvider::getInstance()->save ( QString::fromUtf8 ( argv[1] ),CResourcesProvider::getInstance()->load ( QString::fromUtf8 ( argv[1] ) ) );
    } else {
        QApplication a ( argc, argv );
        CMainWindow window;
        window.show();
        return a.exec();
    }
    return 0;
}

