#pragma once
#include <functional>
#include <unordered_map>

class CGameObject;

class CTypeHandler {
public:
	static CGameObject *create ( QString name );
	static void registerType ( QString name, std::function<CGameObject*() > constructor );
private:
	static std::unordered_map<QString,std::function<CGameObject*() > > constructors;
};
