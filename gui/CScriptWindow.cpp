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
    QString def ( "def "+functionName+"(game):" );
    std::stringstream stream;
    stream<<def.toStdString() <<std::endl;
    for ( QString line:functionCode.split ( "\n" ) ) {
        stream<<"\t"<<line.toStdString() <<std::endl;
    }
    game->getScriptHandler()->executeScript ( QString::fromStdString ( stream.str() ) );
    game->getScriptHandler()->callFunction ( functionName,boost::ref ( game ) );
}
