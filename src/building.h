#ifndef BUILDING_H
#define BUILDING_H
#include "src/building.h"

#include "configurationprovider.h"

#include <src/listitem.h>

class Building : public ListItem {
  Q_OBJECT
  Q_PROPERTY(bool enabled READ isEnabled WRITE setEnabled USER true)
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

protected:
  bool enabled = true;
};
Q_DECLARE_METATYPE(Building)

#endif // BUILDING_H
