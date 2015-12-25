#include "loader/CLoader.h"
#include "templates/thread.h"
#include "core/CTypes.h"

std::shared_ptr<CGame> CGameLoader::loadGame(std::shared_ptr<CGameView> view) {
    std::shared_ptr<CGame> game = std::make_shared<CGame>(view);
    initObjectHandler(game->getObjectHandler());
    initConfigurations(game->getObjectHandler());
    initScriptHandler(game->getScriptHandler(), game);
    return game;
}

void CGameLoader::startGame(std::shared_ptr<CGame> game, QString file, QString player) {
    game->setMap(CMapLoader::loadNewMap(game, file, player));
    vstd::call_later([game]() {
        game->getMap()->ensureSize();
        game->getView()->show();
    });
}

void CGameLoader::changeMap(std::shared_ptr<CGame> game, QString name) {
    vstd::call_later([game, name]() {
        //TODO: implement stop processing events here
        vstd::call_when([game]() {
                            return !game->getMap()->isMoving();
                        },
                        [game, name]() {
                            std::shared_ptr<CPlayer> player = game->getMap()->getPlayer();
                            game->setMap(CMapLoader::loadNewMap(game, name));
                            game->getMap()->setPlayer(player);
                            game->getMap()->ensureSize();
                        });
    });
}

void CGameLoader::initConfigurations(std::shared_ptr<CObjectHandler> handler) {
    for (QString path : CResourcesProvider::getInstance()->getFiles(CONFIG)) {
        handler->registerConfig(path);
    }
}

void CGameLoader::initObjectHandler(std::shared_ptr<CObjectHandler> handler) {
    for (std::pair<QString, std::function<std::shared_ptr<CGameObject>() >> it:CTypes::builders()) {
        handler->registerType(it.first, it.second);
    }
}

void CGameLoader::initScriptHandler(std::shared_ptr<CScriptHandler> handler, std::shared_ptr<CGame> game) {
    for (QString script:CResourcesProvider::getInstance()->getFiles(CResType::SCRIPT)) {
        QString modName = QFileInfo(script).baseName();
        handler->import(modName);
        handler->callFunction(modName + ".load", game);
    }
}
