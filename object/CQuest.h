#pragma once
#include "CGameObject.h"

class CQuest : public CGameObject {
	Q_PROPERTY ( QString description READ getDescription WRITE setDescription USER trues )
public:
	CQuest();
	virtual bool isCompleted();
	QString getDescription() const;
	void setDescription ( const QString &value );

private:
	QString description;
};

