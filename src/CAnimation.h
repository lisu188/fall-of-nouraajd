#pragma once
#include <map>
class QPixmap;
class CAnimation : private std::map<int, std::pair<QPixmap *, int> > {
public:
	CAnimation();
	~CAnimation();
	QPixmap *getImage();
	int getTime();
	int size();

	void next();
	void add ( QPixmap *img, int time );

private:
	int actual;
};
