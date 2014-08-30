#include "animationprovider.h"

#include <src/animation.h>
#include <sstream>
#include <fstream>
#include <QBitmap>
#include <QDebug>
#include <src/tile.h>
#include <map>
#include <src/configurationprovider.h>
#include <mutex>

static inline bool endswith ( std::string const &fullString, std::string const &ending ) {
	if ( fullString.length() >= ending.length() ) {
		return ( 0 == fullString.compare ( fullString.length() - ending.length(), ending.length(), ending ) );
	} else {
		return false;
	}
}
std::map<int, AnimationProvider> AnimationProvider::instances;

Animation *AnimationProvider::getAnim ( std::string path, int size ) {
	static std::mutex mutex;
	std::unique_lock<std::mutex> lock ( mutex );
	if ( instances.find ( size ) == instances.end() ) {
		instances.insert (
		    std::pair<int, AnimationProvider> ( size, AnimationProvider ( size ) ) );
	}
	return instances.at ( size ).getAnimation ( path );
}

AnimationProvider::AnimationProvider ( int size ) : tileSize ( size ) {}

AnimationProvider::~AnimationProvider() {
	for ( iterator it = begin(); it != end(); it++ ) {
		delete ( *it ).second;
	}
	clear();
}

Animation *AnimationProvider::getAnimation ( std::string path ) {
	if ( this->find ( path ) != this->end() ) {
		return this->at ( path );
	}
	loadAnim ( path );
	if ( this->find ( path ) == this->end() ) {
		return 0;
	}
	return getAnimation ( path );
}

void AnimationProvider::loadAnim ( std::string path ) {
	Animation *anim = new Animation();
	QPixmap *img = 0;
	std::map<int, int> timemap;
	Json::Value config = *ConfigurationProvider::getConfig ( path + "time.json" );
	if ( !config.isNull() ) {
		for ( int i = 0; i < config.size(); i++ ) {
			timemap.insert ( std::pair<int, int> ( i, config[i].asInt() ) );
		}
	} else {
		timemap.insert ( std::pair<int, int> ( 0, 250 ) );
	}
	if ( !endswith ( path,"/" ) ) {
		img=getImage ( path+".png" );
		if ( img ) {
			anim->add ( img, timemap.at ( 0 ) );
		}
	} else {
		for ( int i = 0; true; i++ ) {
			std::string result;
			std::ostringstream convert;
			convert << i;
			result = convert.str();
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
	this->insert ( std::pair<std::string, Animation *> ( path, anim ) );
	qDebug() << "Loaded animation:" << path.c_str() << "\n";
}

QPixmap *AnimationProvider::getImage ( std::string path ) {
	QPixmap image ( path.c_str() );
	if ( !image.hasAlphaChannel() && path.find ( "tiles" ) == std::string::npos ) {
		image.setMask ( image.createHeuristicMask() );
	}
	if ( !image.isNull() ) {
		return new QPixmap ( image.scaled ( tileSize, tileSize, Qt::IgnoreAspectRatio,
		                                    Qt::SmoothTransformation ) );
	} else {
		return NULL;
	}
}


