#pragma once
#include "CCreature.h"
class CQuest;
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
	virtual void trade ( CGameObject *object ) override;
	CInteraction *getSelectedAction() const;
	void setSelectedAction ( CInteraction *value );
	CCreature *getEnemy() const;
	void setEnemy ( CCreature *value );
	void setNextMove ( Coords coords );
	virtual Coords getNextMove() override;
	CMarket *getMarket() const;
	void setMarket ( CMarket *value );
	void addQuest ( QString questName );
private:
	void checkQuests();
	CInteraction *selectedAction=0;
	CCreature *enemy=0;
	CMarket *market=0;
	int turn=0;
	Coords next;
	std::set<CQuest*> quests;

};
