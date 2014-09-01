#pragma once
#include <string>
#include <map>
class CAnimation;
class QPixmap;
class CAnimationProvider : private std::map<std::string, CAnimation *> {
public:
	static CAnimation *getAnim ( std::string path, int size );
	virtual ~CAnimationProvider();

private:
	CAnimationProvider ( int size );
	CAnimation *getAnimation ( std::string path );
	void loadAnim ( std::string path );
	QPixmap * getImage ( std::string path );
	int tileSize;
	static std::map<int, CAnimationProvider> instances;
};
