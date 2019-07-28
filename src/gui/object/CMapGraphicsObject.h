#pragma once

#include "gui/object/CGameGraphicsObject.h"

class CMapGraphicsObject : public CGameGraphicsObject {
V_META(CMapGraphicsObject, CGameGraphicsObject,
       V_PROPERTY(CMapGraphicsObject, std::shared_ptr<CMapStringString>, panelKeys, getPanelKeys, setPanelKeys),
       V_METHOD(CMapGraphicsObject, initialize))


public:
    CMapGraphicsObject();

    void render(std::shared_ptr<CGui> gui, std::shared_ptr<SDL_Rect> pos, int frameTime) override;

    std::shared_ptr<CMapStringString> getPanelKeys() {
        return panelKeys;
    };

    void setPanelKeys(std::shared_ptr<CMapStringString> panelKeys) {
        this->panelKeys = panelKeys;
    }

    void initialize() {
        for (auto val:panelKeys->getValues()) {
            auto keyPred = [=](std::shared_ptr<CGui> gui, SDL_Event *event) {
                return event->type == SDL_KEYDOWN && event->key.keysym.sym == val.first[0];
            };
            registerEventCallback(keyPred, [=](std::shared_ptr<CGui> gui, SDL_Event *event) {
                std::shared_ptr<CGamePanel> panel = gui->getGame()->createObject<CGamePanel>(val.second);
                panel->registerEventCallback(keyPred, [=](std::shared_ptr<CGui> gui, SDL_Event *event) {
                    gui->removeObject(panel);
                    return true;
                });
                gui->addObject(panel);
                return true;
            });
        }
    }

private:
    std::shared_ptr<CMapStringString> panelKeys;

};

