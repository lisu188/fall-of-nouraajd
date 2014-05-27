#include "event.h"
#include "scriptmanager.h"

Event::Event()
{

}

Event::Event(const Event &)
{

}

void Event::onEnter()
{
    ScriptManager::getInstance().executeScript(script.toStdString());
}

void Event::onMove()
{

}

void Event::loadFromJson(std::string name)
{

}
QString Event::getScript() const
{
    return script;
}

void Event::setScript(const QString &value)
{
    script = value;
}

