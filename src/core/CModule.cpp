#include "core/CLoader.h"
#include "core/CWrapper.h"
#include "core/CJsonUtil.h"

using namespace boost::python;

int randint(int i, int j) {
    return rand() % (j - i + 1) + i;
}

std::string jsonify(std::shared_ptr<CGameObject> x) {
    return JSONIFY(x);
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
}
