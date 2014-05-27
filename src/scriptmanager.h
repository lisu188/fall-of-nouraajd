#ifndef SCRIPTMANAGER_H
#define SCRIPTMANAGER_H
#include <string>
class ScriptManager
{
public:
    static ScriptManager& getInstance();
    void executeScript(std::string script);
private:
    ScriptManager();
    ScriptManager(ScriptManager&);
};

#endif // SCRIPTMANAGER_H
