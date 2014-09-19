#pragma once
#include <QObject>
class CMap;
class CGuiHandler:public QObject {
	Q_OBJECT
public:
	CGuiHandler ( CMap*map );
private:
    CMap*map;
};
\
