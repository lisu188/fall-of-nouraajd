#include "CScriptWindow.h"
#include "ui_CScriptWindow.h"
#include "CGlobal.h"
#include "CGame.h"

CScriptWindow::CScriptWindow ( CGame *game ) :game ( game ),ui ( new Ui::CScriptWindow ) {
    ui->setupUi ( this );
    this->setVisible ( true );
}

CScriptWindow::~CScriptWindow() {
    delete ui;
}

void CScriptWindow::on_executeButton_clicked() {
    game->getScriptHandler()->callCreatedFunction ( ui->scriptArea->toPlainText(), {"game"} , game );
}
