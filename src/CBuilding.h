#pragma once
#include "CConfigurationProvider.h"
#include <src/map.h>

class CBuilding : public MapObject {
	Q_OBJECT
	Q_PROPERTY ( bool enabled READ isEnabled WRITE setEnabled USER true )
public:
	static CBuilding *createBuilding ( QString name );
	CBuilding();
	CBuilding ( const CBuilding & );
	virtual void onEnter();
	virtual void onMove();
	virtual void onCreate();
	virtual void onDestroy();
	virtual void loadFromJson ( std::string name );
	// PROPERTIES
	bool isEnabled();
	void setEnabled ( bool enabled );

protected:
	bool enabled = true;
};
