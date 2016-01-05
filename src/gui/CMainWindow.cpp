//#include "CGameView.h"
//#include "CMainWindow.h"
////#include "ui_CMainWindow.h"
//
//#include "core/CGame.h"
//
//CMainWindow::CMainWindow() :
//    ui ( std::make_shared<Ui::CMainWindow>() ) {
//    ui->setupUi ( this );
//}
//
//CMainWindow::~CMainWindow() {
//    if ( view ) {
//        vstd::wait_until ( [this]() {
//            return !view->getGame()->getMap()->isMoving();
//        } );
//    }
//}
//
//void CMainWindow::on_pushButton_clicked() {
//    view = std::make_shared<CGameView> ( this->ui->mapType->text(), this->ui->playerType->text() );
//    this->hide();
//}
