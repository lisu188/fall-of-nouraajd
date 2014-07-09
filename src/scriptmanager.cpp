#include "scriptmanager.h"
#include "gamescript.h"
#include <QString>
#include <sstream>

ScriptEngine::~ScriptEngine()
{
    Py_Finalize();
}

void ScriptEngine::executeFile(std::string path)
{
    QFile file((std::string("scripts/").append(path)).c_str());
    if (file.open(QIODevice::ReadOnly)) {
      QByteArray data = file.readAll();
      PyRun_SimpleString(data.data());
      file.close();
    }
}

void ScriptEngine::executeScript(QString script) {
  PyRun_SimpleString(script.toStdString().append("\n").c_str());
  PyErr_Print();
}

QString ScriptEngine::buildCommand(std::initializer_list<std::string> list) {
  QString command;
  int pos = 0;
  for (auto it = list.begin(); it != list.end(); it++, pos++) {
    QString part = (QString::fromStdString(*it));
    part.replace("\"", "\\\"");
    if (pos == 0) {
      command.append(part);
      command.append("(");
    } else {
      command.append("\"");
      command.append(part);
      command.append("\"");
      if (pos < list.size() - 1) {
        command.append(",");
      } else {
        command.append(")");
      }
    }
  }
  return command;
}

void ScriptEngine::executeCommand(std::initializer_list<std::string> list) {
    executeScript(buildCommand(list));
}

PyMODINIT_FUNC PyInit_Game(void) { return PyModule_Create(&GameModule); }

ScriptEngine::ScriptEngine(Map *map) {
  PyImport_AppendInittab("Game", PyInit_Game);
  Py_Initialize();
  PySys_SetPath(L"./scripts");
  PyRun_SimpleString("from Game import *");
  std::stringstream stream;
  stream << std::hex << (unsigned long)map;
  std::string result(stream.str());
  PyObject_SetAttrString(PyImport_ImportModule("__main__"),"map",Py_BuildValue("s",result.c_str()));
  PyMethodDef method;
  for (int i = 0; true; i++) {
    method = GameMethods[i];
    if (method.ml_name == 0) {
      break;
    }
  }
}
