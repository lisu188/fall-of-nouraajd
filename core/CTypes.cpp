#include "core/CTypes.h"

extern void initialize1();

extern void initialize2();

void CTypes::initialize() {
    initialize1();
    initialize2();
}

std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> &CTypes::builders() {
    static std::unordered_map<QString, std::function<std::shared_ptr<CGameObject>() >> reg;
    return reg;
}

std::unordered_map<std::pair<int, int>, std::shared_ptr<CSerializerBase> > &CTypes::serializers() {
    static std::unordered_map<std::pair<int, int>, std::shared_ptr<CSerializerBase>> reg;
    return reg;
}
