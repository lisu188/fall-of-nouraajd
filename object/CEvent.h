#pragma once
#include "CMapObject.h"

class CEvent : public CMapObject,public Visitable {
	Q_OBJECT
	Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
	Q_PROPERTY ( QString eventClass READ getEventClass WRITE setEventClass USER true )
public:
	CEvent();
	CEvent ( const CEvent & );

	bool isEnabled();
	void setEnabled ( bool enabled );
	QString getEventClass();
	void setEventClass ( const QString &value );

	virtual void onEnter ( CGameEvent * );
	virtual void onLeave ( CGameEvent * );
private:
	QString eventClass;
	bool enabled = true;
};
