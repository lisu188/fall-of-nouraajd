//#pragma once
//
//#include "core/CGlobal.h"
//
//class CGameObject;
//
//class ATypeHandler;
//
//class CGame;
//
//class AGamePanel;
//
//class CGuiHandler {
//public:
//    CGuiHandler ( std::shared_ptr<CGame> game );
//
//    void showMessage ( std::string msg );
//
//    std::shared_ptr<AGamePanel> getPanel ( std::string panel );
//
//    void showPanel ( std::string panel );
//
//    void hidePanel ( std::string panel );
//
//    void flipPanel ( std::string panel );
//
//    bool isAnyPanelVisible();
//
//    void refresh();
//
//private:
//    std::map<std::string, std::shared_ptr<AGamePanel>> panels;
//
//    void initPanels();
//
//    std::weak_ptr<CGame> game;
//};
