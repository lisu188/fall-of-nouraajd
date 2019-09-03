#include "core/CLoader.h"
#include "core/CWrapper.h"
#include "core/CJsonUtil.h"

using namespace boost::python;

int randint(int i, int j) {
    return vstd::rand(i, j + 1) % (j - i + 1) + i;//TODO: unify and document exclusive inclusive
}

std::string jsonify(std::shared_ptr<CGameObject> x) {
    return JSONIFY(x);
}

void logger(std::string s) {
    vstd::logger::info(s);//TODO: add script name
}

extern void initModule1();

extern void initModule2();

extern void initModule3();

extern void initModule4();

#define PY_WRAP_GENERIC(fcn) def(#fcn,boost::python::make_function(fcn))

BOOST_PYTHON_MODULE (_game) {

    initModule1();
    initModule2();
    initModule3();
    initModule4();

    PY_WRAP_GENERIC(randint);
    PY_WRAP_GENERIC(jsonify);
    PY_WRAP_GENERIC(logger);
}
