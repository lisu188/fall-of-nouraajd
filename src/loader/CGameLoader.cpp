#include "loader/CLoader.h"

#include "core/CTypes.h"

std::shared_ptr<CGame> CGameLoader::loadGame() {
    std::shared_ptr<CGame> game = std::make_shared<CGame>();
    initObjectHandler(game->getObjectHandler());
    initConfigurations(game->getObjectHandler());
    initScriptHandler(game->getScriptHandler(), game);
    return game;
}

void CGameLoader::startGame(std::shared_ptr<CGame> game, std::string file, std::string player) {
    game->setMap(CMapLoader::loadNewMap(game, file, player));
}

void CGameLoader::changeMap(std::shared_ptr<CGame> game, std::string name) {
    vstd::call_later([game, name]() {
        //TODO: implement stop processing events here
        vstd::call_when([game]() {
                            return !game->getMap()->isMoving();
                        },
                        [game, name]() {
                            std::shared_ptr<CPlayer> player = game->getMap()->getPlayer();
                            game->setMap(CMapLoader::loadNewMap(game, name));
                            game->getMap()->setPlayer(player);
                        });
    });
}

void CGameLoader::initConfigurations(std::shared_ptr<CObjectHandler> handler) {
    for (std::string path : CResourcesProvider::getInstance()->getFiles(CONFIG)) {
        handler->registerConfig(path);
    }
}

void CGameLoader::initObjectHandler(std::shared_ptr<CObjectHandler> handler) {
    for (std::pair<std::string, std::function<std::shared_ptr<CGameObject>() >> it:*CTypes::builders()) {
        handler->registerType(it.first, it.second);
    }
}

void CGameLoader::initScriptHandler(std::shared_ptr<CScriptHandler> handler, std::shared_ptr<CGame> game) {
    for (std::string script:CResourcesProvider::getInstance()->getFiles(CResType::SCRIPT)) {
        std::string mod_name = boost::filesystem::path(script).stem().string();
        handler->import(mod_name);
        handler->call_function(vstd::join({mod_name, "load"}, "."), game);
    }
}
