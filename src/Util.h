#pragma once
#include <QRunnable>
#include <QVariant>
#include <functional>
#include <sstream>
#include <string>

#define PROP(type, name, bean)                                                 \
private:                                                                       \
  Q_PROPERTY(type name READ get##bean WRITE set##bean USER true)               \
  type name = 0;                                                               \
                                                                               \
public:                                                                        \
  type get##bean() { return name; }                                            \
  void set##bean(type name) { this->name = name; }                             \
                                                                               \
private:

#define PROPERTY_ACCESSOR                                                      \
public:                                                                        \
  Q_INVOKABLE void setProperty(QString name, QVariant property) {              \
    this->QObject::setProperty(name.toStdString().c_str(), property);          \
  }                                                                            \
  Q_INVOKABLE QVariant property(QString name) const {                          \
    return this->QObject::property(name.toStdString().c_str());                \
  }                                                                            \
  Q_INVOKABLE void setStringProperty(QString name, QString value) {            \
    this->setProperty(name, value);                                            \
  }                                                                            \
  Q_INVOKABLE void setBoolProperty(QString name, bool value) {                 \
    this->setProperty(name, value);                                            \
  }                                                                            \
  Q_INVOKABLE void setNumericProperty(QString name, int value) {               \
    this->setProperty(name, value);                                            \
  }                                                                            \
  Q_INVOKABLE QString getStringProperty(QString name) const {                  \
    return this->property(name).toString();                                    \
  }                                                                            \
  Q_INVOKABLE bool getBoolProperty(QString name) const {                       \
    return this->property(name).toBool();                                      \
  }                                                                            \
  Q_INVOKABLE int getNumericProperty(QString name) const {                     \
    return this->property(name).toInt();                                       \
  }                                                                            \
  Q_INVOKABLE void incProperty(QString name, int value) {                      \
    this->setNumericProperty(name, this->getNumericProperty(name) + value);    \
  }

#define PY_PROPERTY_ACCESSOR(CLASS)                                            \
  .def("getStringProperty", &CLASS::getStringProperty)                         \
      .def("getNumericProperty", &CLASS::getNumericProperty)                   \
      .def("getBoolProperty", &CLASS::getBoolProperty)                         \
      .def("setStringProperty", &CLASS::setStringProperty)                     \
      .def("setNumericProperty", &CLASS::setNumericProperty)                   \
      .def("setBoolProperty", &CLASS::setBoolProperty)                         \
      .def("incProperty", &CLASS::incProperty)

struct Coords {
  Coords() { x = y = z = 0; }
  Coords(int x, int y, int z) : x(x), y(y), z(z) {}
  int x, y, z;
  bool operator==(const Coords &other) const {
    return (x == other.x && y == other.y && z == other.z);
  }
  bool operator<(const Coords &other) const {
    if (x < other.x) {
      return true;
    }
    if (y < other.y && x == other.x) {
      return true;
    }
    if (z < other.z && x == other.x && y == other.y) {
      return true;
    }
    return false;
  }
  int getDist(Coords a) {
    double x = this->x - a.x;
    x *= x;
    double y = this->y - a.y;
    y *= y;
    return sqrt(x + y);
  }
};

struct CoordsHasher {
  std::size_t operator()(const Coords &coords) const {
    using std::size_t;
    int a = (size_t)coords.x;
    int b = (size_t)coords.y;
    int c = (size_t)coords.z;
    return (size_t)(a ^ b) ^ (b ^ c) ^ (a ^ c);
  }
};

inline bool str2int(int &i, char const *s) {
  char c;
  std::stringstream ss(s);
  ss >> i;
  if (ss.fail() || ss.get(c)) {
    // not an integer
    return false;
  }
  return true;
}

inline QString toLower(const QString &s) {
  QString result;
  std::locale loc;
  for (int i = 0; i < s.length(); ++i) {
    result += std::tolower(s.at(i), loc);
  }
  return result;
}

template <typename T> QString to_string(const T &n) {
  std::ostringstream stm;
  stm << n;
  return QString(stm.str().c_str());
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

template <class T> class Comparer {
public:
  bool operator()(T *first, T *second) {
    if (!first) {
      return false;
    }
    if (!second) {
      return true;
    }
    return first->compare(second);
  }
};
