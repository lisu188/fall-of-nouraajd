#ifndef SCRIPTMANAGER_H
#define SCRIPTMANAGER_H
#include <string>
class ScriptManager
{
public:
    static ScriptManager& getInstance();
    void executeScript(std::string script);
    void executeCommand(std::initializer_list<std::string> list);

private:
    ScriptManager();
    ScriptManager(ScriptManager&);
};

#endif // SCRIPTMANAGER_H
