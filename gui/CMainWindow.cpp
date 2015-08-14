#include "CGameView.h"
#include "CMainWindow.h"
#include "ui_CMainWindow.h"
#include "CThreadUtil.h"
#include "CGame.h"
#include "CMap.h"

CMainWindow::CMainWindow () :
    ui ( std::make_shared<Ui::CMainWindow>() ) {
    ui->setupUi ( this );
}

CMainWindow::~CMainWindow() {
    if ( view ) {
        CThreadUtil::wait_until ( [this]() {
            return !view->getGame()->getMap()->isMoving();
        } );
    }
}

void CMainWindow::on_pushButton_clicked() {
    view=std::make_shared<CGameView> ( this->ui->mapType->text(),this->ui->playerType->text() );
    this->hide();
}
