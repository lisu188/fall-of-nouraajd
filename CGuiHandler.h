#pragma once
#include <QObject>
class CMap;
class AGamePanel;
class CGuiHandler:public QObject {
	Q_OBJECT
public:
	CGuiHandler ( CMap*map );
	void showMessage ( QString msg );
	AGamePanel *getPanel ( QString panel );
	bool isAnyPanelVisible();
	void refresh();
private:
	std::map<QString,AGamePanel*> panels;
	void initPanels();
	CMap*map;
};

