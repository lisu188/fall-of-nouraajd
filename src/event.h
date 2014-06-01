#include "map.h"

#ifndef EVENT_H
#define EVENT_H

class Event : public MapObject {
  Q_OBJECT
  Q_PROPERTY(QString script READ getScript WRITE setScript USER true)
  Q_PROPERTY(bool enabled READ isEnabled WRITE setEnabled USER true)
public:
  Event();
  Event(const Event &);
  void onEnter();
  void onMove();
  void loadFromJson(std::string name);
  // PROPERTIES
  QString getScript() const;
  void setScript(const QString &value);
  bool isEnabled();
  void setEnabled(bool enabled);

private:
  bool enabled = true;
  QString script;
};
Q_DECLARE_METATYPE(Event)
#endif // EVENT_H
