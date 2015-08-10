#include "CScriptWindow.h"
#include "ui_CScriptWindow.h"
#include "CGlobal.h"
#include "CGame.h"

CScriptWindow::CScriptWindow ( std::shared_ptr<CGame> game ) :game ( game ),ui ( new Ui::CScriptWindow ) {
    ui->setupUi ( this );
    ui->executeButton->setShortcut ( QKeySequence ( Qt::Key_Control,Qt::Key_E ) );
    this->setVisible ( true );
}

CScriptWindow::~CScriptWindow() {
    delete ui;
}

void CScriptWindow::on_executeButton_clicked() {
    game->getScriptHandler()->callCreatedFunction ( ui->scriptArea->toPlainText(), {"game"} , game );
}
