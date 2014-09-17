#pragma once
#include <QMainWindow>

namespace Ui {
class CMainWindow;
}

class CMainWindow : public QMainWindow {
	Q_OBJECT

public:
	explicit CMainWindow ( QWidget *parent = 0 );
	~CMainWindow();

private:
	Q_SLOT void on_pushButton_clicked();

private:
	Ui::CMainWindow *ui;
};
