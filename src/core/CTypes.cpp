#include "core/CTypes.h"



std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *CTypes::builders() {
    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>() >> reg;
    return &reg;
}

std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> *
CTypes::serializers() {
    static std::unordered_map<std::pair<boost::typeindex::type_index, boost::typeindex::type_index>, std::shared_ptr<CSerializerBase>> reg;
    return &reg;
}

bool CTypes::is_map_type(boost::typeindex::type_index index) {
    return vstd::ctn(*map_types(), index);
}

bool CTypes::is_pointer_type(boost::typeindex::type_index index) {
    return vstd::ctn(*pointer_types(), index);
}

bool CTypes::is_array_type(boost::typeindex::type_index index) {
    return vstd::ctn(*array_types(), index);
}

std::unordered_set<boost::typeindex::type_index> *CTypes::map_types() {
    static std::unordered_set<boost::typeindex::type_index> _map_types;
    return &_map_types;
}

std::unordered_set<boost::typeindex::type_index> *CTypes::array_types() {
    static std::unordered_set<boost::typeindex::type_index> _array_types;
    return &_array_types;
}

std::unordered_set<boost::typeindex::type_index> *CTypes::pointer_types() {
    static std::unordered_set<boost::typeindex::type_index> _pointer_types;
    return &_pointer_types;
}