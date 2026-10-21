# rextracto

extrakto for Rex. See `README.md` for what it does and how users set it up.

## Layout

- `rextracto.py`: the filter engine (`Extrakto`, `FilterDef`, `get_lines`, `extract`), the `extract` subcommand, capture over the `rex` CLI (`capture`, `window_blocks`), and the fzf loop (`pick`). Standard library only, Python 3.10+.
- `rextracto.conf`: the default filters, in extrakto's `extrakto.conf` format.
- `lua/rextracto.lua`: the Rex module. `setup(opts)` defines the action, which opens the script in a floating layer; `command_for` turns options into the script's flags (option `foo_bar` becomes `--foo-bar`). It runs in Rex's server Lua (Lua 5.1, gopher-lua), so it must stay plain 5.1.
- `tests/test_rextracto.py`: unittest. `AssetTests` compares `extract` output byte for byte with extrakto's fixtures in `tests/assets`; the rest mock Rex and fzf. `tests/test_lua.lua`: stubs the `rex` global and checks the action.

## Behavior to keep

- The filter engine and `extract` flags match upstream extrakto; keep the asset tests passing, and keep reading `~/.config/extrakto/extrakto.conf` for compatibility.
- Keys and defaults follow extrakto's `@extrakto_*` options.
- Insert goes through a `block.event` paste, so bracketed paste works; Ctrl-E writes to the pane with `write`.
- Rex doesn't give modules their file name, so `setup` needs `opts.root`; the `debug.getinfo` fallback only works when loaded from a checkout.
- New `setup` options need a matching argparse flag, a README row, and a test.

## Checks

```sh
python3 -m unittest discover -s tests -v
lua tests/test_lua.lua
ruff check . && ruff format --check .
```

For a live check, create a throwaway session (`rex new`), open the script with `rex api call session.new_layer` as the Lua action does, drive fzf with `rex send` and `rex send-key`, and destroy the session afterwards. Don't use the user's visible sessions.

## Commits and releases

- Use Conventional Commits: `<type>(<scope>): <description>` with `feat`, `fix`, `refactor`, `docs`, `test`, `chore` or `ci`.
- Each push to `main` runs CI; when it passes, `feat`, `fix` and breaking commits (`!` or `BREAKING CHANGE`) since the last tag produce a new tag and GitHub release. Other types don't release.
- Use generic names and fixtures in tests and docs; never reference real projects, hosts or people.
