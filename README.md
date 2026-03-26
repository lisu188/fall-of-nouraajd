# fall-of-nouraajd
c++ dark fantasy game
<br/><br/>
<img src="./screenshots/maze.png" width="50%" height="300"><img src="./screenshots/fight.png" width="50%" height="300">
## controls
<pre>
arrows - move
space - skip turn / close window
i - inventory
j - quest log
c - character sheet
s - save
tab - open/close python console
</pre>
## running
### ubuntu
<pre>
sudo apt install python3.11 python3.11-dev
./configure.sh
cmake --build cmake-build-release --target _game -j$(nproc)
python3 play.py
</pre>

### mcp server (engine api)
<pre>
cmake --build cmake-build-release --target _game -j$(nproc)
# start HTTP MCP server (defaults to 127.0.0.1:8765)
python3 mcp.py
# or build the extension on demand and run
python3 mcp.py --build
</pre>
The HTTP server exposes a unified `engine` surface from both `game` and `_game` via MCP tools:
- `engine_list`
- `engine_call`
- `engine_handle_call`

To use stdio transport instead (required by some Codex flows), run from the repository root:
<pre>
python3 mcp.py --stdio --repo-root . --build-dir cmake-build-release
</pre>
The command also works from `cmake-build-release/mcp.py` if you prefer launching from the build directory.

### testing
Running tests is **mandatory** after any code change.
From the repository root, run:
<pre>
cmake --build cmake-build-release --target _game -j$(nproc)
python3 test.py
</pre>
Data validation tests run without needing the compiled `_game` module, but
other tests require it to be built.
