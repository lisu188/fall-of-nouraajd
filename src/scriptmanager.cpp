#include "scriptmanager.h"
#include "gamescript.h"
#include <QString>

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

void ScriptManager::executeCommand(std::initializer_list<std::string> list){
    QString command;
    int pos=0;
    for(auto it=list.begin();it!=list.end();it++,pos++){
        QString part=(QString::fromStdString(*it));
        part.replace("\"","\\\"");
        if(pos==0){
            command.append("Game.");
            command.append(part);
            command.append("(");
        }else{
            command.append("\"");
            command.append(part);
            command.append("\"");
            if(pos<list.size()-1){
                command.append(",");
            }else{
                command.append(")");
            }
        }
    }
    executeScript(command.toStdString());
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
    PyMethodDef method;
    for(int i=0;true;i++){
        method=GameMethods[i];
        if(method.ml_name==0){
            break;
        }
        executeScript(std::string(method.ml_name).append("=Game.").append(method.ml_name));
    }
}
