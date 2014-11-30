#pragma once
#include <QObject>
#include <QString>
#include <map>

class CGameObject;
class ATypeHandler;
class CMap;
class AGamePanel;
class CGuiHandler:public QObject {
	Q_OBJECT
public:
	CGuiHandler ( CMap*map );
	void showMessage ( QString msg );
	AGamePanel *getPanel ( QString panel );
	void showPanel ( QString panel );
	bool isAnyPanelVisible();
	void refresh();
private:
	std::map<QString,AGamePanel*> panels;
	void initPanels();
	CMap*map;
};
