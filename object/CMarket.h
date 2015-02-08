#pragma once
#include "CGameObject.h"
#include <set>
class CItem;
class CMarket : public CGameObject {
	Q_OBJECT
	Q_PROPERTY ( QVariantList items READ getItems WRITE setItems USER true )
public:
	CMarket();
	~CMarket();
	void add ( CItem*item );
	void remove ( CItem*item );
	std::set<CItem*> getTradeItems();
	void setItems ( QVariantList items );
	QVariantList getItems ();
private:
	std::set<CItem*> items;
};

