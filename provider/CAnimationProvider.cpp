#include "CAnimationProvider.h"
#include "CUtil.h"
#include "provider/CProvider.h"
#include "handler/CHandler.h"
#include "object/CObject.h"

std::shared_ptr<CAnimation> CAnimationProvider::getAnim ( QString path ) {
    static CAnimationProvider instance;
    return instance.getAnimation ( path );
}

CAnimationProvider::CAnimationProvider ( )  {

}

CAnimationProvider::~CAnimationProvider() {

}

std::shared_ptr<CAnimation> CAnimationProvider::getAnimation ( QString path ) {
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
    std::shared_ptr<CAnimation> anim=std::make_shared<CAnimation>();
    std::shared_ptr<QPixmap> img;
    std::map<int, int> timemap;
    QString time="time.json";

    QJsonArray config;
    if ( path.endsWith ( "/" ) ) {
        CConfigurationProvider::getConfig ( path + time ).toArray();
    }
    if ( !config.isEmpty() ) {
        for (  int i = 0; i < config.size(); i++ ) {
            timemap.insert ( std::make_pair ( i, config[i].toInt() ) );
        }
    } else {
        timemap.insert (  std::make_pair ( 0, 250 ) );
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
    this->insert ( std::make_pair ( path, anim ) );
    qDebug() << "Loaded animation:" << path   << "\n";
}

std::shared_ptr<QPixmap> CAnimationProvider::getImage ( QString path ) {
    std::shared_ptr<QFile> file = CResourcesProvider::getInstance()->getResource ( path );
    QPixmap image;
    if ( file && file->open ( QIODevice::ReadOnly ) ) {
        image.loadFromData ( file->readAll() );
    }
    if ( !image.isNull() ) {
        if ( !image.hasAlphaChannel() && !path.contains ( "tiles" ) ) {
            image.setMask ( image.createHeuristicMask() );
        }
        return std::make_shared<QPixmap> ( image.scaled ( 50, 50, Qt::IgnoreAspectRatio,
                                           Qt::SmoothTransformation ) );
    }
    return nullptr;
}

CAnimation::CAnimation () {

}

CAnimation::~CAnimation() {

}

std::shared_ptr<QPixmap> CAnimation::getImage() {
    return at ( actual ).first;
}

int CAnimation::getTime() {
    if ( size() == 1 ) {
        return -1;
    }
    return at ( actual ).second;
}

int CAnimation::size() {
    return std::map<int, std::pair<std::shared_ptr<QPixmap>, int> >::size();
}

void CAnimation::next() {
    actual++;
    actual = actual % size();
}

void CAnimation::add ( std::shared_ptr<QPixmap> img, int time ) {
    insert (  std::make_pair (
                  size(),  std::make_pair ( img, time ) ) );
}
