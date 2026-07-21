# Vendored Lua

- Version: 5.4.8
- Source: https://www.lua.org/ftp/lua-5.4.8.tar.gz (contents of `src/`, unmodified)
- Tarball SHA-256: `4f18ddae154e793e46eeab727c59ef1c0c0c2b744e7b94219710d76f530629ae`
- License: MIT (see LICENSE)

Built as the static `lua_vendor` library by the root CMakeLists.txt; `lua.c` (REPL) and
`luac.c` (bytecode compiler) are excluded from the build. Used by the Lua plugin runtime
(`src/handler/CLuaHandler.*`). To upgrade, replace these files with the new release's `src/`
contents and update this file.
