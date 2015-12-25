#pragma once
extern "C" {
PyObject *PyInit__game();
PyObject *PyInit__core();
}

#ifdef DEBUG_MODE
extern "C" {
    PyObject* PyInit_debug();
}
#endif
