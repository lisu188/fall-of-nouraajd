#include "building.h"
#include <QDebug>
#include <src/gamescene.h>
#include <src/playerstatsview.h>
#include <src/monster.h>
#include <src/configurationprovider.h>
#include <src/scriptmanager.h>

Building *Building::createBuilding(QString name) {
  return dynamic_cast<Building *>(MapObject::createMapObject(name));
}

Building::Building() : ListItem(0, 0, 0, 2) {}

Building::Building(const Building &) {}

void Building::onEnter() {
    if(script.isEmpty())return;
    ScriptManager::getInstance()->executeFile(script.toStdString());
    ScriptManager::getInstance()->executeScript(QString("THIS=\"").append(QString::fromStdString(name)).append("\""));
    ScriptManager::getInstance()->executeScript("onEnter()");
}

void Building::onMove() {
    if(script.isEmpty())return;
    ScriptManager::getInstance()->executeFile(script.toStdString());
    ScriptManager::getInstance()->executeScript(QString("THIS=\"").append(QString::fromStdString(name)).append("\""));
    ScriptManager::getInstance()->executeScript("onMove()");
}

void Building::onCreate()
{
    if(script.isEmpty())return;
    ScriptManager::getInstance()->executeFile(script.toStdString());
    ScriptManager::getInstance()->executeScript(QString("THIS=\"").append(QString::fromStdString(name)).append("\""));
    ScriptManager::getInstance()->executeScript("onCreate()");
}

void Building::onDestroy()
{
    if(script.isEmpty())return;
    ScriptManager::getInstance()->executeFile(script.toStdString());
    ScriptManager::getInstance()->executeScript(QString("THIS=\"").append(QString::fromStdString(name)).append("\""));
    ScriptManager::getInstance()->executeScript("onDestroy()");
}

void Building::loadFromJson(std::string name) {
  this->typeName = name;
  Json::Value config =
      (*ConfigurationProvider::getConfig("config/object.json"))[name];
  this->setAnimation(config.get("animation", "").asString());
  script=config.get("script","").asCString();
}

bool Building::isEnabled() { return enabled; }

void Building::setEnabled(bool enabled) { this->enabled = enabled; }
QString Building::getScript() const
{
    return script;
}

void Building::setScript(const QString &value)
{
    script = value;
}

Teleporter::Teleporter() {}

Teleporter::Teleporter(const Teleporter &teleporter) : Teleporter() {}

void Teleporter::onEnter() {
  if (!enabled)
    return;
  Teleporter *teleporter =
      dynamic_cast<Teleporter *>(getMap()->getObjectByName(exit.toStdString()));
  if (!teleporter) {
    return;
    qDebug() << "Teleporter exit configured to" << exit << "but don`t exist!"
             << "\n";
  }
  GameScene::getPlayer()->moveTo(teleporter->getPosX(), teleporter->getPosY(),
                                 teleporter->getPosZ(), true);
}

void Teleporter::onMove() {}

QString Teleporter::getExit() const { return exit; }

void Teleporter::setExit(const QString &value) { exit = value; }
