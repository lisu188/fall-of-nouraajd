#pragma once
#define GAME_PROPERTY(CLASS)\
  Q_DECLARE_METATYPE(std::shared_ptr<CLASS>)\
  Q_DECLARE_METATYPE(std::set<std::shared_ptr<CLASS>>)\
  typedef std::map<QString,std::shared_ptr<CLASS>> CLASS##Map;\
  Q_DECLARE_METATYPE(CLASS##Map)\

#define PY_SAFE(x) try{x}catch(...){qDebug()<<"";PyErr_Print();PyErr_Clear();}
#define PY_SAFE_RET(x) try{x}catch(...){qDebug()<<"";PyErr_Print();PyErr_Clear();return nullptr;}

