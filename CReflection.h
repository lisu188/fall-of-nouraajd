#pragma once
#include <list>
#include <QObject>
#include <QDebug>
#include <mutex>
#include <set>
#define PP_CAT(a, b) PP_CAT_I(a, b)
#define PP_CAT_I(a, b) PP_CAT_II(~, a ## b)
#define PP_CAT_II(p, res) res

#define UNIQUE_NAME(base) PP_CAT(base, __LINE__)

#define REFLECT(CLASS) \
Q_DECLARE_METATYPE(CLASS) \
Q_DECLARE_METATYPE(CLASS*) \
CReflectionHelper<CLASS> UNIQUE_NAME(CReflectionHelper##CLASS##BASE) ; \
CReflectionHelper<CLASS*> UNIQUE_NAME(CReflectionHelper##CLASS##POINTER) ; \
 
class CReflection {
public:
	static CReflection * getInstance();
	bool checkInheritance ( QString base, QString inherited );
	template<typename T>
	void registerType() {
		static std::mutex mutex;
		std::unique_lock<std::mutex> lock ( mutex );
		metaTypes.insert ( qRegisterMetaType<T>() );
	}
	template<typename T>
	std::list<T> getInherited() {
		std::list<T> objects;
		const QMetaObject *mObject=QMetaType::metaObjectForType ( qRegisterMetaType<T>() );
		if ( mObject ) {
			QString base=mObject->className();
			for ( int type:metaTypes ) {
				mObject=QMetaType::metaObjectForType ( type );
				if ( mObject && checkInheritance ( base,mObject->className() ) ) {
					QString typeName=mObject->className();
					int typeId=QMetaType::type ( typeName.toStdString().c_str() );
					T object= ( T ) QMetaType::create ( typeId );
					objects.push_back (  object );
				}
			}
		} else {
			qFatal ( "No registered object" );
		}
		return objects;
	}
	std::set<int> metaTypes;
private:
	CReflection() {}
};

template<class T>
class CReflectionHelper {
public:
	CReflectionHelper() {
		CReflection::getInstance()->registerType<T>();
	}
};
