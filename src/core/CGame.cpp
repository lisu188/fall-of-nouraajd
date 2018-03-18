#include "core/CGame.h"
#include "core/CLoader.h"
#include "gui/CGui.h"

CGame::CGame() {

}

CGame::~CGame() {

}

void CGame::changeMap(std::string file) {
    CGameLoader::changeMap(this->ptr<CGame>(), file);
}

std::shared_ptr<CMap> CGame::getMap() const {
    return map;
}

void CGame::setMap(std::shared_ptr<CMap> map) {
    this->map = map;
}

std::shared_ptr<CGuiHandler> CGame::getGuiHandler() {
    return guiHandler.get([this]() {
        return std::make_shared<CGuiHandler>(this->ptr<CGame>());
    });
}

std::shared_ptr<CScriptHandler> CGame::getScriptHandler() {
    return scriptHandler.get([]() {
        return std::make_shared<CScriptHandler>();
    });
}

std::shared_ptr<CObjectHandler> CGame::getObjectHandler() {
    return objectHandler.get([]() {
        return std::make_shared<CObjectHandler>();
    });
}

void CGame::loadPlugin(std::function<std::shared_ptr<CPlugin>()> plugin) {
    plugin()->load(this->ptr<CGame>());
}

std::shared_ptr<CGui> CGame::getGui() const {
    return _gui;
}

void CGame::setGui(std::shared_ptr<CGui> _gui) {
    CGame::_gui = _gui;
}

std::shared_ptr<CSlotConfig> CGame::getSlotConfiguration() {
    return slotConfiguration.get([this]() {
        return createObject<CSlotConfig>("slotConfiguration");
    });
}

std::shared_ptr<CLootHandler> CGame::getLootHandler() {
    return lootHandler.get([this]() {
        return std::make_shared<CLootHandler>(this->ptr<CGame>());
    });
}
