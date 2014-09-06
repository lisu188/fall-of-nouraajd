#pragma once
#include <QString>
#include <map>
class CAnimation;
class QPixmap;
class CAnimationProvider : private std::map<QString, CAnimation *> {
public:
	static CAnimation *getAnim ( QString path, int size );
	virtual ~CAnimationProvider();

private:
	CAnimationProvider ( int size );
	CAnimation *getAnimation ( QString path );
	void loadAnim ( QString path );
	QPixmap * getImage ( QString path );
	int tileSize;
	static std::map<int, CAnimationProvider> instances;
};
