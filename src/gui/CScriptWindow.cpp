//#include "CScriptWindow.h"
//#include "core/CGame.h"
//
//CScriptWindow::CScriptWindow ( std::shared_ptr<CGame> game ) : game ( game ), ui ( new Ui::CScriptWindow ) {
//    ui->setupUi ( this );
//    ui->executeButton->setShortcut ( QKeySequence ( "Ctrl+E" ) );
//    this->setVisible ( true );
//}
//
//CScriptWindow::~CScriptWindow() {
//    delete ui;
//}
//
//void CScriptWindow::on_executeButton_clicked() {
//    game->getScriptHandler()->callCreatedFunction ( ui->scriptArea->toPlainText(), {"game"}, game );
//}
