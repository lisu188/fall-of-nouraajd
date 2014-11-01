#include <QApplication>
#include <QDebug>
#include <QThreadPool>
#include <QtGlobal>
#include <mutex>
#include "CMainWindow.h"
#include "CGameView.h"
#include "handler/CHandler.h"
#include <stdio.h>
#include <signal.h>

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
#ifndef ANDROID
void terminateHandler () {
	PyErr_Print();
	abort();
}
#else
void terminateHandler ( int ) {
	PyObject *ptype, *pvalue, *ptraceback;
	PyErr_Fetch ( &ptype, &pvalue, &ptraceback );
	std::string pStrErrorMessage = boost::python::extract<std::string> ( pvalue );
	qWarning ( pStrErrorMessage.c_str() );
	abort();
}
#endif

#ifndef ANDROID
void installHandler() {
	qInstallMessageHandler ( messageHandler );
	std::set_terminate ( terminateHandler );
}
#else
void installHandler() {
	signal ( SIGABRT, terminateHandler );
}
#endif

int main ( int argc, char *argv[] ) {
	installHandler();
	QApplication a ( argc, argv );
	QThreadPool::globalInstance()->setMaxThreadCount ( 16 );
	QThreadPool::globalInstance()->setExpiryTimeout ( 30000 );
	CMainWindow window;
	window.show();
	return a.exec();
}

