#pragma once

#include "core/CGlobal.h"

class CGame;

namespace Ui {
    class CScriptWindow;
}

class CScriptWindow : public QWidget {

public:
    CScriptWindow ( std::shared_ptr<CGame> game );

    ~CScriptWindow();

    Q_SLOT void on_executeButton_clicked();

private:
    std::shared_ptr<CGame> game;
    Ui::CScriptWindow *ui;
};

