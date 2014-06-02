#ifndef BUILDING_H
#define BUILDING_H
#include "src/building.h"

#include "configurationprovider.h"

#include <src/listitem.h>

class Building : public ListItem {
  Q_OBJECT
  Q_PROPERTY(bool enabled READ isEnabled WRITE setEnabled USER true)
  Q_PROPERTY(QString script READ getScript WRITE setScript USER true)
public:
  static Building *createBuilding(QString name);
  Building();
  Building(const Building &);
  virtual void onEnter();
  virtual void onMove();
  virtual void onCreate();
  virtual void onDestroy();
  virtual void loadFromJson(std::string name);
  // PROPERTIES
  bool isEnabled();
  void setEnabled(bool enabled);
  QString getScript() const;
  void setScript(const QString &value);

protected:
  bool enabled = true;
  QString script;
};
Q_DECLARE_METATYPE(Building)

#endif // BUILDING_H
