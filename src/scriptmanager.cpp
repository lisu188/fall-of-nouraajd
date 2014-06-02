#include "scriptmanager.h"
#include "gamescript.h"
#include <QString>

ScriptManager::ScriptManager(ScriptManager &) {}

ScriptManager *ScriptManager::getInstance() {
  static ScriptManager instance;
  return &instance;
}

void ScriptManager::executeFile(std::string path)
{
    QFile file((std::string(":/scripts/").append(path)).c_str());
    if (file.open(QIODevice::ReadOnly)) {
      QByteArray data = file.readAll();
      PyRun_SimpleString(data.data());
      file.close();
    }
}

void ScriptManager::executeScript(QString script) {
  PyRun_SimpleString(script.toStdString().c_str());
}

QString ScriptManager::buildCommand(std::initializer_list<std::string> list) {
  QString command;
  int pos = 0;
  for (auto it = list.begin(); it != list.end(); it++, pos++) {
    QString part = (QString::fromStdString(*it));
    part.replace("\"", "\\\"");
    if (pos == 0) {
      command.append("Game.");
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

void ScriptManager::executeCommand(std::initializer_list<std::string> list) {
    executeScript(buildCommand(list));
}

PyMODINIT_FUNC PyInit_Game(void) { return PyModule_Create(&GameModule); }

ScriptManager::ScriptManager() {
  PyImport_AppendInittab("Game", PyInit_Game);
  Py_Initialize();
  PySys_SetPath(L"./scripts");
  PyRun_SimpleString("import Game");
  PyMethodDef method;
  for (int i = 0; true; i++) {
    method = GameMethods[i];
    if (method.ml_name == 0) {
      break;
    }
    executeScript(QString::fromStdString(
        std::string(method.ml_name).append("=Game.").append(method.ml_name)));
  }
}
