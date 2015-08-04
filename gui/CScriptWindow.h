#pragma once
#include "CGlobal.h"
class CGame;

namespace Ui {
    class CScriptWindow;
}

class CScriptWindow : public QWidget {
    Q_OBJECT
public:
    CScriptWindow ( std::shared_ptr<CGame> game );
    ~CScriptWindow();
    Q_SLOT void on_executeButton_clicked();
private:
    std::shared_ptr<CGame> game;
    Ui::CScriptWindow *ui;
};

