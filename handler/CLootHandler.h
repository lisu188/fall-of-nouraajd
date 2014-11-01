#pragma once
#include <string>
#include <map>
#include <set>
#include <QString>
#include <QObject>
class CItem;
class CMap;
class CLootHandler : public QObject,private std::map<QString, int> {
	Q_OBJECT
public:
	std::set<CItem *> getLoot ( int value ) const;
	CLootHandler ( CMap *map ) ;
	~CLootHandler();
private:
	std::set<CItem *> calculateLoot ( int value ) const;
	const CMap* map;
};
