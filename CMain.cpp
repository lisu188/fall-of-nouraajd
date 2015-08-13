#include "CGlobal.h"
#include "gui/CGui.h"
#include "CTypes.h"

static void messageHandler ( QtMsgType type, const QMessageLogContext &context,
                             const QString &msg ) {
    static std::mutex mutex;
    std::unique_lock<std::mutex> lock ( mutex );
    QByteArray localMsg = msg.toLocal8Bit();
    switch ( type ) {
    case QtDebugMsg:
        fprintf ( stderr, "%s\n", localMsg.constData() );
        break;
    case QtInfoMsg:
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
        std::set_terminate ( [] ( )-> void {
            PyErr_Print();
            abort();
        } );
    }
} a;

template<typename T>
void register_type() {
    CTypes::register_type<T>();
}

void register_types() {
    register_type< Stats >();
    register_type< Damage >();
    register_type< CGameObject >();
    register_type< CMapObject >();
    register_type< CWeapon >();
    register_type< CArmor >();
    register_type< CPotion >();
    register_type< CBuilding >();
    register_type< CItem >();
    register_type< CPlayer >();
    register_type< CMonster >();
    register_type< CTile >();
    register_type< CInteraction >();
    register_type< CSmallWeapon >();
    register_type< CHelmet >();
    register_type< CBoots >();
    register_type< CBelt >();
    register_type< CGloves >();
    register_type< CEvent >();
    register_type< CScroll >();
    register_type< CEffect >();
    register_type< CMarket >();
    register_type< CTrigger >();
    register_type< CQuest >();
}

int main ( int argc, char *argv[] ) {
    register_types();
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

