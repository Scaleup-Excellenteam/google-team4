# Autocomplete Engine — CLI + Flask UI

A minimal autocomplete system with:
- **DB module** behind a CRUD interface (SQLite or in-memory).
- **Backend** (index + search + normalization) orchestrated by `Engine`.
- **Frontends**: a CLI and a Flask “GUI”.

This README shows how to set it up on **Linux/macOS** and **Windows (PowerShell)**.

---

## Project layout

```

project-root/
├─ Archive/                # your .txt corpus (top-level, next to src/)
└─ src/
├─ backend/             # engine, index, search, DB adapters
└─ frontend/            # CLI + Flask UI

````

> Put your `.txt` files (or folders of `.txt`) under `Archive/`.

---

## Requirements

- Python **3.10+**
- `pip` to install dependencies (Flask, etc.)

### Create a virtual environment & install

**Linux/macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask
# or: pip install -r requirements.txt  # if provided
````

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install flask
# or: pip install -r requirements.txt
```

---

## Build the index + create/seed the DB

Run these **from `project-root/src`**.

**Linux/macOS**

```bash
cd src
python -m frontend --build --roots ../Archive \
  --cache ../artifacts.pkl \
  --db "sqlite:///../corpus.sqlite"
```

**Windows (PowerShell)**

```powershell
cd .\src
python -m frontend --build --roots ..\Archive `
  --cache ..\artifacts.pkl `
  --db "sqlite:///..\corpus.sqlite"
```

* `--roots` points to your `Archive/` directory.
* `--db` uses SQLite via DSN (path is relative to `src`).
* `--cache` (optional) saves a pickled index for faster loads later.

> If you skip `--cache`, use the web app in `--build` mode (next section).

---

## Run the Flask UI

### Option A — Load the cached index (fast start)

**Linux/macOS**

```bash
python -m frontend.web --load \
  --cache ../artifacts.pkl \
  --db "sqlite:///../corpus.sqlite" \
  --host 127.0.0.1 --port 8000
```

**Windows (PowerShell)**

```powershell
python -m frontend.web --load `
  --cache ..\artifacts.pkl `
  --db "sqlite:///..\corpus.sqlite" `
  --host 127.0.0.1 --port 8000
```

Open: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Option B — Rebuild on startup (no cache needed)

**Linux/macOS**

```bash
python -m frontend.web --build \
  --roots ../Archive \
  --db "sqlite:///../corpus.sqlite" \
  --host 127.0.0.1 --port 8000
```

**Windows (PowerShell)**

```powershell
python -m frontend.web --build `
  --roots ..\Archive `
  --db "sqlite:///..\corpus.sqlite" `
  --host 127.0.0.1 --port 8000
```

---

## CLI frontend (optional)

**Linux/macOS**

```bash
python -m frontend --load --cache ../artifacts.pkl --db "sqlite:///../corpus.sqlite" --repl
```

**Windows (PowerShell)**

```powershell
python -m frontend --load --cache ..\artifacts.pkl --db "sqlite:///..\corpus.sqlite" --repl
```

Type queries at the prompt; `Enter` runs; blank line exits.

---

## Advanced knobs

* Tokenization/windowing:

  * `--unit {line,paragraph,window} --window-size N --window-step M`
* ACX index (if enabled in your build):

  * Build: `--acx-out ../index.acx`
  * Load:  `--acx ../index.acx`

---

## Troubleshooting

* **ImportError: attempted relative import beyond top-level package**
  Run commands from `src` and prefer absolute imports in `frontend` (e.g., `from backend.engine import Engine`).

* **HTTP 500 on `/api/complete` with `KeyError: <sid>`**
  Your SQLite DB isn’t seeded. Rebuild using `--build` so the DB is populated before serving, or ensure `Engine.build()` seeds the DB.

* **No results appear**
  Confirm there are `.txt` files in `Archive/`. Also verify DB rows:

  ```bash
  # from src (Linux/macOS)
  python - <<'PY'
  ```

from backend.DB.corpusdb import CorpusDB
db = CorpusDB("../corpus.sqlite")
print("rows in DB:", db.count())
PY



- **Port already in use**  
Change `--port`, e.g., `--port 8080`.

- **Pickle errors about lambdas**  
If using `--cache`, make sure the index class implements custom pickling (drops any lambda getters), or simply run the web app with `--build`.

---

## Dev workflow tips

- Frontends (CLI/Flask) should depend **only** on `backend.engine.Engine`.
- The DB is behind a `CorpusStore` CRUD interface (SQLite now; in-memory also available).  
Swapping stores shouldn’t require frontend changes.

---

## Further reading

