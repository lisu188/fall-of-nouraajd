#include "scriptmanager.h"
#include "gamescript.h"

ScriptManager::ScriptManager(ScriptManager &)
{

}


ScriptManager &ScriptManager::getInstance()
{
    static ScriptManager instance;
    return instance;
}

void ScriptManager::executeScript(std::string script)
{
    PyRun_SimpleString(script.c_str());
}

PyMODINIT_FUNC
PyInit_Game(void)
{
    return PyModule_Create(&GameModule);
}

ScriptManager::ScriptManager()
{
    PyImport_AppendInittab("Game", PyInit_Game);
    Py_Initialize();
    PyRun_SimpleString("import Game");
}
