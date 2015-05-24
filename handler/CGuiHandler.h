#pragma once
#include "CGlobal.h"

class CGameObject;
class ATypeHandler;
class CGame;
class AGamePanel;
class CGuiHandler {
public:
    CGuiHandler ( std::shared_ptr<CGame> game );
    void showMessage ( QString msg );
    std::shared_ptr<AGamePanel> getPanel ( QString panel );
    void showPanel ( QString panel );
    void hidePanel ( QString panel );
    void flipPanel ( QString panel );
    bool isAnyPanelVisible();
    void refresh();
private:
    std::map<QString,std::shared_ptr<AGamePanel>> panels;
    void initPanels();
    std::weak_ptr<CGame> game;
};
