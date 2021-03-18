/*
fall-of-nouraajd c++ dark fantasy game
Copyright (C) 2019  Andrzej Lis

This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#include <utility>

#include "core/CLoader.h"
#include "core/CWrapper.h"
#include "core/CJsonUtil.h"

using namespace boost::python;

int randint(int i, int j) {
    return vstd::rand(i, j);//TODO: unify and document exclusive inclusive
}

std::string jsonify(std::shared_ptr<CGameObject> x) {
    return JSONIFY(x);
}

void logger(std::string s) {
    vstd::logger::info(std::move(s));//TODO: add script name
}

extern void initModule1();

extern void initModule2();

extern void initModule3();

extern void initModule4();

extern void initModule5();


#define PY_WRAP_GENERIC(fcn) def(#fcn,boost::python::make_function(fcn))

BOOST_PYTHON_MODULE (_game) {

    initModule1();
    initModule2();
    initModule3();
    initModule4();
    initModule5();

    PY_WRAP_GENERIC(randint);
    PY_WRAP_GENERIC(jsonify);
    PY_WRAP_GENERIC(logger);
}
