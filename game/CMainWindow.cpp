#include "CGameView.h"
#include "CMainWindow.h"
#include "ui_CMainWindow.h"

CMainWindow::CMainWindow ( QWidget *parent ) :
	QMainWindow ( parent ),
	ui ( new Ui::CMainWindow ) {
	ui->setupUi ( this );
}

CMainWindow::~CMainWindow() {
	delete view;
	delete ui;
}

void CMainWindow::on_pushButton_clicked() {
	view=new CGameView ( this->ui->mapType->text(),this->ui->playerType->text() );
	this->hide();
}
