#pragma once
#include "CGlobal.h"
class CGame;

namespace Ui {
class CScriptWindow;
}

class CScriptWindow : public QWidget {
    Q_OBJECT
public:
    CScriptWindow ( CGame *game );
    ~CScriptWindow();
    Q_SLOT void on_executeButton_clicked();
private:
    CGame*game=nullptr;
    Ui::CScriptWindow *ui;
};

