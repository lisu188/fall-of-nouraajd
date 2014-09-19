#pragma once
#include <string>
#include <map>
#include <set>
#include <QString>
#include <QObject>
class CItem;
class CMap;
class CLootProvider : public QObject,private std::map<QString, int> {
	Q_OBJECT
public:
    std::set<CItem *> *getLoot ( int value )const;
    CLootProvider ( CMap *map ) ;
	~CLootProvider();
private:
    std::set<CItem *> *calculateLoot ( int value )const;
    const CMap* map;
};
