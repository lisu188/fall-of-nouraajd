#include "gameview.h"
#include "mainwindow.h"
#include "ui_mainwindow.h"

MainWindow::MainWindow ( QWidget *parent ) :
	QMainWindow ( parent ),
	ui ( new Ui::MainWindow ) {
	ui->setupUi ( this );
}

MainWindow::~MainWindow() {
	delete ui;
}

void MainWindow::on_pushButton_clicked() {
	GameView*view=new GameView ( this->ui->mapType->text().toStdString(),this->ui->playerType->text().toStdString() );
	this->hide();
}
