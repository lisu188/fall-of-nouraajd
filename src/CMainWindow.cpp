#include "CGameView.h"
#include "CMainWindow.h"
#include "ui_CMainWindow.h"

CMainWindow::CMainWindow ( QWidget *parent ) :
	QMainWindow ( parent ),
	ui ( new Ui::CMainWindow ) {
	ui->setupUi ( this );
}

CMainWindow::~CMainWindow() {
	delete ui;
}

void CMainWindow::on_pushButton_clicked() {
	CGameView*view=new CGameView ( this->ui->mapType->text(),this->ui->playerType->text() );
	view->setParent ( this );
	this->hide();
}
