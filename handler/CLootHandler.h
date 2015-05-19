#pragma once
#include <string>
#include <map>
#include <set>
#include <QString>
#include <QObject>
class CItem;
class CMap;
class CLootHandler :private std::map<QString, int> {
public:
    std::set<CItem *> getLoot ( int value ) const;
    CLootHandler ( CMap *map ) ;
    ~CLootHandler();
private:
    std::set<CItem *> calculateLoot ( int value ) const;
    CMap* map;
};
