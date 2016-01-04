#pragma once

#include "core/CGlobal.h"

class CGameView;
namespace Ui {
    class CMainWindow;
}

class CMainWindow : public QMainWindow {


public:
    explicit CMainWindow();

    ~CMainWindow();

private:
    Q_SLOT void on_pushButton_clicked();

    std::shared_ptr<Ui::CMainWindow> ui;
    std::shared_ptr<CGameView> view;
};
