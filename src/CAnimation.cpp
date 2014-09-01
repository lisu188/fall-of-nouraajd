#include <QPixmap>
#include "CAnimation.h"

CAnimation::CAnimation() { actual = 0; }

CAnimation::~CAnimation() {
	for ( iterator it = begin(); it != end(); it++ ) {
		delete ( *it ).second.first;
	}
	clear();
}

QPixmap *CAnimation::getImage() { return at ( actual ).first; }

int CAnimation::getTime() {
	if ( size() == 1 ) {
		return -1;
	}
	return at ( actual ).second;
}

int CAnimation::size() {
	return std::map<int, std::pair<QPixmap *, int> >::size();
}

void CAnimation::next() {
	actual++;
	actual = actual % size();
}

void CAnimation::add ( QPixmap *img, int time ) {
	insert ( std::pair<int, std::pair<QPixmap *, int> > (
	             size(), std::pair<QPixmap *, int> ( img, time ) ) );
}
