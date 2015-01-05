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
CReflectionHelper<CLASS> UNIQUE_NAME(CReflectionHelper##CLASS##BASE)(#CLASS) ;

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
