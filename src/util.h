#ifndef UTIL_H
#define UTIL_H
#include <sstream>
#include <QVariant>
#include <QRunnable>
#include <functional>
#include <string>
#define PROPERTY_ACCESSOR \
void setStringProperty ( std::string name,std::string value ) {\
    this->setProperty ( name.c_str(),QString::fromStdString ( value ) );\
}\
void setBoolProperty ( std::string name,bool value ) {\
    this->setProperty ( name.c_str(),value );\
}\
void setNumericProperty ( std::string name,int value ) {\
    this->setProperty ( name.c_str(),value );\
}\
std::string getStringProperty ( std::string name ) {\
    return this->property ( name.c_str() ).toString().toStdString();\
}\
bool getBoolProperty ( std::string name ) {\
    return this->property ( name.c_str() ).toBool();\
}\
int getNumericProperty ( std::string name ) {\
    return this->property ( name.c_str() ).toInt();\
}\
void incProperty ( std::string name,int value ) {\
    this->setNumericProperty ( name,this->getNumericProperty ( name )+value );\
}\
 
#define PY_PROPERTY_ACCESSOR(CLASS)\
.def ( "getStringProperty",&CLASS::getStringProperty )\
.def ( "getNumericProperty",&CLASS::getNumericProperty )\
.def ( "getBoolProperty",&CLASS::getBoolProperty )\
.def ( "setStringProperty",&CLASS::setStringProperty )\
.def ( "setNumericProperty",&CLASS::setNumericProperty )\
.def ( "setBoolProperty",&CLASS::setBoolProperty )\
.def ( "incProperty",&CLASS::incProperty )\
 
inline bool endswith ( std::string const &fullString, std::string const &ending ) {
	if ( fullString.length() >= ending.length() ) {
		return ( 0 == fullString.compare ( fullString.length() - ending.length(), ending.length(), ending ) );
	} else {
		return false;
	}
}

template <typename T> inline std::string to_string ( const T &n ) {
	std::ostringstream stm;
	stm << n;
	return stm.str();
}

inline bool checkInheritance ( std::string base, std::string inherited ) {
	int classId = QMetaType::type ( inherited.append ( "*" ).c_str() );
	const QMetaObject *metaObject = QMetaType::metaObjectForType ( classId );
	while ( metaObject ) {
		std::string className = metaObject->className();
		if ( className.compare ( base ) == 0 ) {
			break;
		}
		metaObject = metaObject->superClass();
	}
	return metaObject != 0;
}

inline bool str2int ( int &i, char const *s ) {
	char              c;
	std::stringstream ss ( s );
	ss >> i;
	if ( ss.fail() || ss.get ( c ) ) {
		// not an integer
		return false;
	}
	return true;
}

class GameTask : public QObject, public QRunnable {
	Q_OBJECT
public:
	GameTask ( std::function<void() > task ) { this->task = task; }

	void run() {
		Q_EMIT started();
		task();
		Q_EMIT finished();
	}

	Q_SIGNAL void started();
	Q_SIGNAL void finished();

private:
	std::function<void() > task;
};
#endif // UTIL_H
