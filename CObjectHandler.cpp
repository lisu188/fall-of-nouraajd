#include "CScriptEngine.h"
#include "CConfigurationProvider.h"
#include "CCreature.h"
#include "CInteraction.h"
#include "CMap.h"
#include "CResourcesHandler.h"
#include "CObjectHandler.h"
#include "CTile.h"
#include "Stats.h"
#include <QDebug>
#include <QDirIterator>
#include <QJsonArray>
#include <QMetaProperty>

CObjectHandler::CObjectHandler(CMap *map) : QObject(map), map(map) {
  QSet<QString> files;
  for (QString path : CResourcesHandler::getInstance()->getFiles(CONFIG)) {
    if (path.endsWith(".json")) {
      files.insert(path.startsWith(":/") ? path.mid(2) : path);
    }
  }
  files.insert(map->getMapPath() + "/config.json");
  for (const auto &path : files) {
    QJsonObject config = CConfigurationProvider::getConfig(path).toObject();
    for (auto it = config.begin(); it != config.end(); ++it) {
      if (objectConfig.contains(it.key())) {
        qFatal("Duplicate object configuration %s", qPrintable(it.key()));
      }
      objectConfig[it.key()] = it.value();
    }
  }
}

CGameObject *CObjectHandler::_createObject(QString type) const {
  if (!objectConfig.contains(type)) {
    qFatal("No object configuration for %s", qPrintable(type));
  }
  QJsonObject config = objectConfig[type].toObject();
  QString class_name = config["class"].toString();
  if (class_name.isEmpty() &&
      (config.contains("manaCost") || config.contains("effect") ||
       config.contains("anim"))) {
    class_name = "CInteraction";
  }
  QString handler_name = config["handler"].toString("CTypeHandler");
  if (handler_name == "CTypeHandler" &&
      !QMetaType::type(qPrintable(class_name)) &&
      QMetaType::type(qPrintable("C" + class_name))) {
    class_name.prepend("C");
  }
  if (class_name.startsWith("game.interaction.")) {
    boost::python::object definition =
                  CScriptEngine::getInstance()
                      ->getObject("game")
                      .attr("interaction")
                      .attr(class_name.section('.', -1).toStdString().c_str());
              if (PyFunction_Check(definition.ptr())) {
                class_name = "CInteraction";
                handler_name = "CTypeHandler";
              }
  }
  ATypeHandler *type_handler = ATypeHandler::getHandler(handler_name);
  if (!type_handler) {
    qFatal("Unknown type handler %s", qPrintable(handler_name));
  }
  CGameObject *object = type_handler->create(class_name);
  if (!object) {
    qFatal("Cannot create object %s (%s)", qPrintable(type),
           qPrintable(class_name));
  }
    if (auto *mapObject = dynamic_cast<CMapObject *>(object)) mapObject->map = map;
  else object->setMap(map);
  object->setObjectType(type);
  object->setObjectName(
      QString::number(reinterpret_cast<quintptr>(object), 16));
  object->setParent(const_cast<CObjectHandler *>(this));
  QJsonObject properties =
      config.contains("properties") ? config["properties"].toObject() : config;
  properties.remove("class");
  properties.remove("handler");
  if (properties.contains("anim") && !properties.contains("animation")) {
    properties["animation"] = properties.take("anim");
  }
  for (auto it = properties.begin(); it != properties.end(); ++it) {
    setProperty(object, it.key(), it.value());
  }
  if (CCreature *creature = dynamic_cast<CCreature *>(object)) {
    QJsonObject stats = properties["stats"].toObject();
    for (auto it = stats.begin(); it != stats.end(); ++it)
      creature->getStats()->setProperty(it.key(), it.value().toVariant());
    creature->attribChange();
    for (QJsonValue action : properties["actions"].toArray())
      creature->addAction(createMapObject<CInteraction *>(action.toString()));
    for (QJsonValue item : properties["items"].toArray())
      creature->addItem(createMapObject<CItem *>(item.toString()));
    QJsonObject equipped = properties["inventory"].toObject();
    for (auto it = equipped.begin(); it != equipped.end(); ++it)
      creature->setItem(it.key().toInt(),
                        createMapObject<CItem *>(it.value().toString()));
    if (!creature->getLevel())
      creature->levelUp();
    creature->heal(0);
    creature->addMana(0);
  }
  return object;
}

void CObjectHandler::setProperty(CGameObject *object, QString key,
                                 QJsonValue value) const {
  QMetaProperty property = getProperty(object, key);
  if (value.isObject() && property.isValid() &&
      QString(property.typeName()) == "Stats") {
    Stats stats;
    QJsonObject fields = value.toObject();
    for (auto it = fields.begin(); it != fields.end(); ++it) {
      stats.setProperty(it.key(), it.value().toVariant());
    }
    property.write(object, QVariant(QMetaType::type("Stats"), &stats));
    return;
  }
  object->setProperty(qPrintable(key), value.toVariant());
}
QMetaProperty CObjectHandler::getProperty(CGameObject *object, QString name) const {
  int index = object->metaObject()->indexOfProperty(qPrintable(name));
  return index < 0 ? QMetaProperty() : object->metaObject()->property(index);
}
void CObjectHandler::logProperties(CGameObject *object) const {
  for (int i = 0; i < object->metaObject()->propertyCount(); ++i) {
    QMetaProperty property = object->metaObject()->property(i);
    if (property.isUser()) {
      qDebug() << property.name() << property.read(object);
    }
  }
}

const QJsonObject *CObjectHandler::getObjectConfig() const { return &objectConfig; }

