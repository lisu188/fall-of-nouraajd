// Build-only compatibility: restore the immediate parent registration macro.
#pragma once
#include "CReflection.h"
#undef REFLECT
#define REFLECT(CLASS) \
Q_DECLARE_METATYPE(CLASS) \
Q_DECLARE_METATYPE(CLASS*) \
CReflectionHelper<CLASS> UNIQUE_NAME(CReflectionHelper##CLASS##BASE) ; \
CReflectionHelper<CLASS*> UNIQUE_NAME(CReflectionHelper##CLASS##POINTER) ; \
