#ifndef SCRIPTMANAGER_H
#define SCRIPTMANAGER_H
#include <QObject>
#include <string>

class Map;

class ScriptEngine {
public:
  void executeFile(std::string path);
  void executeScript(QString script);
  void executeCommand(std::initializer_list<std::string> list);
  QString buildCommand(std::initializer_list<std::string> list);
  ScriptEngine(Map *map);
  ~ScriptEngine();
};

#endif // SCRIPTMANAGER_H
