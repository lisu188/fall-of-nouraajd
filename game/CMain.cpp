#include <QApplication>
#include <QDebug>
#include <QThreadPool>
#include <QtGlobal>
#include <mutex>
#include "CMainWindow.h"
#include "CGameView.h"
#include <stdio.h>

void messageHandler ( QtMsgType type, const QMessageLogContext &context,
                      const QString &msg ) {
	static std::mutex mutex;
	std::unique_lock<std::mutex> lock ( mutex );
	QByteArray localMsg = msg.toLocal8Bit();
	switch ( type ) {
	case QtDebugMsg:
		fprintf ( stderr, "%s\n", localMsg.constData() );
		break;
	case QtWarningMsg:
		// fprintf(stderr, "Warning: %s (%s:%u, %s)\n", localMsg.constData(),
		// context.file, context.line, context.function);
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

int main ( int argc, char *argv[] ) {
	Q_INIT_RESOURCE ( config );
	Q_INIT_RESOURCE ( images );
	Q_INIT_RESOURCE ( scripts );
	Q_INIT_RESOURCE ( maps );
	qInstallMessageHandler ( messageHandler );
	QApplication a ( argc, argv );
	QThreadPool::globalInstance()->setMaxThreadCount ( 16 );
	QThreadPool::globalInstance()->setExpiryTimeout ( 30000 );
	CMainWindow window;
	window.show();
	return a.exec();
}

