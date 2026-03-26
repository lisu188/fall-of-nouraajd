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
python3 scripts/mcp_engine_server.py
</pre>
The server exposes a unified `engine` surface from both `game` and `_game` via MCP tools:
- `engine_list`
- `engine_call`
- `engine_handle_call`

### testing
Running tests is **mandatory** after any code change.
From the repository root, run:
<pre>
cmake --build cmake-build-release --target _game -j$(nproc)
python3 test.py
</pre>
Data validation tests run without needing the compiled `_game` module, but
other tests require it to be built.
