#include "CAnimationProvider.h"

#include "CAnimation.h"
#include <sstream>
#include <fstream>
#include <QBitmap>
#include <QDebug>
#include "CTile.h"
#include <map>
#include "CConfigurationProvider.h"
#include <mutex>
#include "Util.h"

CAnimation *CAnimationProvider::getAnim ( QString path ) {
	static std::mutex mutex;
	static CAnimationProvider instance;
	std::unique_lock<std::mutex> lock ( mutex );
	return instance.getAnimation ( path );
}

CAnimationProvider::CAnimationProvider ( )  {}

CAnimationProvider::~CAnimationProvider() {
	for ( iterator it = begin(); it != end(); it++ ) {
		delete ( *it ).second;
	}
	clear();
}

CAnimation *CAnimationProvider::getAnimation ( QString path ) {
	if ( this->find ( path ) != this->end() ) {
		return this->at ( path );
	}
	loadAnim ( path );
	if ( this->find ( path ) == this->end() ) {
		return 0;
	}
	return getAnimation ( path );
}

void CAnimationProvider::loadAnim ( QString path ) {
	CAnimation *anim = new CAnimation();
	QPixmap *img = 0;
	std::map<int, int> timemap;
	QString time="time.json";


	QJsonArray config;
	if ( path.endsWith ( "/" ) ) {
		CConfigurationProvider::getConfig ( path + time ).toArray();
	}
	if ( !config.isEmpty() ) {
		for (  int i = 0; i < config.size(); i++ ) {
			timemap.insert ( std::pair<int, int> ( i, config[i].toInt() ) );
		}
	} else {
		timemap.insert ( std::pair<int, int> ( 0, 250 ) );
	}
	if ( ! path.endsWith ( "/" ) ) {
		img=getImage ( path+".png" );
		if ( img ) {
			anim->add ( img, timemap.at ( 0 ) );
		}
	} else {
		for ( int i = 0; true; i++ ) {
			std::ostringstream convert;
			convert << i;
			QString result
			    = QString::fromStdString ( convert.str() );
			img=getImage ( path + result + ".png" );
			if ( !img ) {
				break;
			}
			int frame;
			if ( timemap.size() == 1 ) {
				frame = timemap.at ( 0 );
			} else {
				frame = timemap.at ( i );
			}
			anim->add ( img, frame );
		}
	}
	if ( anim->size() == 0 ) {
		return;
	}
	this->insert ( std::pair<QString, CAnimation *> ( path, anim ) );
	qDebug() << "Loaded animation:" << path   << "\n";
}

QPixmap *CAnimationProvider::getImage ( QString path ) {
	QPixmap image ( path );
	if ( !image.hasAlphaChannel() && !path.contains ( "tiles" ) ) {
		image.setMask ( image.createHeuristicMask() );
	}
	if ( !image.isNull() ) {
		return new QPixmap ( image.scaled ( 50, 50, Qt::IgnoreAspectRatio,
		                                    Qt::SmoothTransformation ) );
	} else {
		return NULL;
	}
}

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
