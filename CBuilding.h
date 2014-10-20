#pragma once
#include "CConfigurationProvider.h"
#include"CMap.h"

class CBuilding : public CMapObject,public Visitable {
	Q_OBJECT
	Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
public:
	CBuilding();
	CBuilding ( const CBuilding & );
	virtual ~CBuilding();

	bool isEnabled();
	void setEnabled ( bool enabled );

    virtual void onEnter(CGameEvent *);
    virtual void onLeave(CGameEvent *);

protected:
	bool enabled = true;
};
