#pragma once

#include "object/CMarket.h"
#include "object/CGameObject.h"

class CGuiHandler : public CGameObject {
V_META(CGuiHandler, CGameObject, vstd::meta::empty())

public:
    CGuiHandler();

    CGuiHandler(std::shared_ptr<CGame> game);

    void showMessage(std::string message);

    bool showDialog(std::string message);

    void showTrade(std::shared_ptr<CMarket> market);
private:
    std::weak_ptr<CGame> _game;
};
