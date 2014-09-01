#ifndef CONFIGURATIONPROVIDER_H
#define CONFIGURATIONPROVIDER_H
#include <lib/json/json.h>
#include <string>

class CConfigurationProvider : private std::map<std::string, Json::Value *> {
public:
	static Json::Value *getConfig ( std::string path );

private:
	CConfigurationProvider();
	~CConfigurationProvider();
	Json::Value *getConfiguration ( std::string path );
	void loadConfig ( std::string path );
};

#endif // CONFIGURATIONPROVIDER_H
