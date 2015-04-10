#pragma once
#include "CMapObject.h"

class CEvent : public CMapObject,public Visitable {
	Q_OBJECT
	Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
public:
	CEvent();

	bool isEnabled();
	void setEnabled ( bool enabled );

	virtual void onEnter ( CGameEvent * );
	virtual void onLeave ( CGameEvent * );
private:
	bool enabled = true;
};
