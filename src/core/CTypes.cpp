//fall-of-nouraajd c++ dark fantasy game
//Copyright (C) 2019  Andrzej Lis
//
//This program is free software: you can redistribute it and/or modify
//        it under the terms of the GNU General Public License as published by
//the Free Software Foundation, either version 3 of the License, or
//(at your option) any later version.
//
//This program is distributed in the hope that it will be useful,
//        but WITHOUT ANY WARRANTY; without even the implied warranty of
//MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//GNU General Public License for more details.
//
//You should have received a copy of the GNU General Public License
//along with this program.  If not, see <https://www.gnu.org/licenses/>.
#include "core/CTypes.h"
#include "core/CGame.h"


std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>()>> *CTypes::builders() {
    static std::unordered_map<std::string, std::function<std::shared_ptr<CGameObject>() >> reg;
    return &reg;
}

std::unordered_map<boost::typeindex::type_index, std::function<void(std::shared_ptr<CGameObject>,
                                                                    std::string, boost::any)>> *CTypes::setters() {
    static std::unordered_map<boost::typeindex::type_index, std::function<void(std::shared_ptr<CGameObject>,
                                                                               std::string, boost::any)>> reg;
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