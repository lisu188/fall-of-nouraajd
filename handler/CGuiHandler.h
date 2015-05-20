#pragma once
#include <QObject>
#include <QString>
#include <map>

class CGameObject;
class ATypeHandler;
class CGame;
class AGamePanel;
class CGuiHandler {
public:
    CGuiHandler ( CGame *game );
    void showMessage ( QString msg );
    AGamePanel *getPanel ( QString panel );
    void showPanel ( QString panel );
    void hidePanel ( QString panel );
    void flipPanel ( QString panel );
    bool isAnyPanelVisible();
    void refresh();
private:
    std::map<QString,AGamePanel*> panels;
    void initPanels();
    CGame *game;
};
