#pragma once

#include "CMapObject.h"

class Stats;

class CEffect :public CGameObject {
    Q_OBJECT
    Q_PROPERTY ( int duration READ getDuration WRITE setDuration )
    Q_PROPERTY ( bool buff READ isBuff WRITE setBuff )
public:
    CEffect();
    virtual ~CEffect();
    int getTimeLeft();
    int getTimeTotal();
    bool apply ( CCreature *creature );
    Stats *getBonus();
    void setBonus ( Stats *value );
    int getDuration();
    void setDuration ( int duration );
    virtual bool onEffect();
    bool isBuff() const;
    void setBuff ( bool value );
    CCreature *getCaster() ;
    void setCaster ( CCreature *value );
    CCreature *getVictim() ;
    void setVictim ( CCreature *value );
private:
    int timeLeft=0;
    int timeTotal=0;
    Stats *bonus=0;
    CCreature *caster=0;
    CCreature *victim=0;
    int duration=0;
    bool buff=false;
};
