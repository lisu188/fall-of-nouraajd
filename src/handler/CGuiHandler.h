#pragma once

#include "object/CGameObject.h"

class CGuiHandler : public CGameObject {
V_META(CGuiHandler, CGameObject, vstd::meta::empty())

public:
    CGuiHandler() {

    }

    CGuiHandler(std::shared_ptr<CGame> game) : _game(game) {

    }

    void showMessage(std::string message) {
        vstd::logger::debug(message);
    }

private:
    std::weak_ptr<CGame> _game;
};
