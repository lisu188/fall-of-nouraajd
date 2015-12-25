#pragma once

#ifdef DEBUG_MODE
#define force_inline
#else
#define force_inline __attribute__((always_inline))
#endif