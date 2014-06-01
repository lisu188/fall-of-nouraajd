#ifndef UTIL_H
#define UTIL_H
#include <sstream>
#include <QVariant>
#include <QRunnable>
#include <functional>
#include <string>
template <typename T> inline std::string to_string(const T &n) {
  std::ostringstream stm;
  stm << n;
  return stm.str();
}

inline bool checkInheritance(std::string base, std::string inherited) {
  int classId = QMetaType::type(inherited.append("*").c_str());
  const QMetaObject *metaObject = QMetaType::metaObjectForType(classId);
  while (metaObject) {
    std::string className = metaObject->className();
    if (className.compare(base) == 0) {
      break;
    }
    metaObject = metaObject->superClass();
  }
  return metaObject != 0;
}

class GameTask : public QObject, public QRunnable {
  Q_OBJECT
public:
  GameTask(std::function<void()> task) { this->task = task; }

  void run() {
    Q_EMIT started();
    task();
    Q_EMIT finished();
  }

  Q_SIGNAL void started();
  Q_SIGNAL void finished();

private:
  std::function<void()> task;
};
#endif // UTIL_H
