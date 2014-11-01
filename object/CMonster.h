#pragma once

#include "CCreature.h"

class CMonster : public CCreature {
	Q_OBJECT
public:
	CMonster();
	CMonster ( const CMonster & );
	virtual ~CMonster();
	virtual void onTurn ( CGameEvent * ) override;
	virtual void levelUp() override;
	virtual std::set<CItem *> getLoot() override;
	virtual Coords getNextMove();
};
