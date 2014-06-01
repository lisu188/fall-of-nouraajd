#ifndef SCRIPTMANAGER_H
#define SCRIPTMANAGER_H
#include <QObject>
#include <string>
class ScriptManager : public QObject {
  Q_OBJECT
public:
  static ScriptManager *getInstance();
  Q_INVOKABLE void executeScript(QString script);
  Q_INVOKABLE void executeCommand(std::initializer_list<std::string> list);
  Q_INVOKABLE QString buildCommand(std::initializer_list<std::string> list);
private:
  ScriptManager();
  ScriptManager(ScriptManager &);
};

#endif // SCRIPTMANAGER_H
