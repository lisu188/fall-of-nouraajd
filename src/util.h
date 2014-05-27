#ifndef UTIL_H
#define UTIL_H
#include <sstream>
#include <QVariant>
namespace util
{
template < typename T > std::string to_string(const T& n)
{
    std::ostringstream stm ;
    stm << n ;
    return stm.str() ;
}
}
#endif // UTIL_H
