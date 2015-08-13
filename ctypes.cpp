#include "CTypes.h"

std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> &CTypes::registry() {
    static std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> reg;
    return reg;
}
