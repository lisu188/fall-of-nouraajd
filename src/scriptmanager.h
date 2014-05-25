#ifndef SCRIPTMANAGER_H
#define SCRIPTMANAGER_H

class ScriptManager
{
public:
    static ScriptManager& getInstance()
    {
        static ScriptManager instance;
        return instance;
    }
private:
    ScriptManager();
    ScriptManager(ScriptManager&);
};

#endif // SCRIPTMANAGER_H
