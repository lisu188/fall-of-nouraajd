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
    QString functionCode=ui->scriptArea->toPlainText();
    QString functionName=QString ( "FUNC" )+to_hex ( std::hash<QString>() ( functionCode ) );
    game->getScriptHandler()->addFunction<CGame*> ( functionName,functionCode, {"game"} ) ( game );
}
