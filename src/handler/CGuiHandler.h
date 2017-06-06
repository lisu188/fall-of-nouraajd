#pragma once

#include "object/CGameObject.h"

class CGuiHandler : public CGameObject {
V_META(CGuiHandler, CGameObject, vstd::meta::empty())

public:
    CGuiHandler();

    CGuiHandler(std::shared_ptr<CGame> game);

    void showMessage(std::string message);

private:
    std::weak_ptr<CGame> _game;
};
