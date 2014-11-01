#pragma once
#include "CCreature.h"

class CPlayer : public CCreature {
	Q_OBJECT
	friend class PlayerStatsView;
public:
	CPlayer();
	CPlayer ( const CPlayer & );
	virtual ~CPlayer();
	virtual void onTurn ( CGameEvent * ) override;
	virtual void onDestroy ( CGameEvent * ) override;
	virtual CInteraction *selectAction() override;
	virtual void fight ( CCreature *creature ) override;
	CInteraction *getSelectedAction() const;
	void setSelectedAction ( CInteraction *value );
	CCreature *getEnemy() const;
	void setEnemy ( CCreature *value );
	void setNextMove ( Coords coords );
	virtual Coords getNextMove() override;
private:
	CInteraction *selectedAction=0;
	CCreature *enemy=0;
	int turn=0;
	Coords next;
};
