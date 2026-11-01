# Setup

Commands below are for Windows (`cmd`). macOS/Linux differences are noted inline.
Expect ~45 minutes, most of it downloads, and ~15 GB of free disk space.

Qdrant runs in Docker, Ollama runs natively (better hardware detection), and the
backend and frontend run directly on the machine for development. A full Docker
setup is also available in `docker-compose.yml` (see the README).

---

## 1. Prerequisites

| Tool | Version | Download |
|---|---|---|
| Python | 3.11+ | python.org/downloads (tick **"Add Python to PATH"**) |
| Node.js | 20+ | nodejs.org (LTS) |
| Docker Desktop | any | docker.com/products/docker-desktop |
| Ollama | any | ollama.com/download |

> macOS/Linux: `docker` + `docker compose` is enough instead of Docker Desktop.
> Ollama: `curl -fsSL https://ollama.com/install.sh | sh`

Clone into a path without spaces or non-ASCII characters (e.g. `C:\projects\mercek`):

```cmd
git clone https://github.com/cgrayd/mercek.git C:\projects\mercek
cd C:\projects\mercek
```

---

## 2. Start Qdrant

Make sure Docker Desktop is running, then:

```cmd
docker compose up -d qdrant
```

Check: http://localhost:6333/dashboard should open.

---

## 3. Pull the model

```cmd
ollama pull qwen3.5:4b
```

~2.6 GB. With 32 GB of RAM, `qwen3.5:9b` gives noticeably better results (set
`MERCEK_LLM_MODEL` accordingly, see step 4).

Quick speed test:

```cmd
ollama run --think=false --verbose qwen3.5:4b "Introduce yourself in one sentence."
```

`--think=false` matters: Qwen3.5 is a reasoning model and Ollama enables thinking by
default, which makes even simple prompts take minutes. Mercek disables it in code
(`MERCEK_LLM_DUSUNME=false`).

The `eval rate` line shows your real speed. 10-15 tok/s is normal; below 3 tok/s the
model does not fit in RAM, so switch to `qwen3.5:1.7b`.

---

## 4. Backend

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> macOS/Linux: `source .venv/bin/activate`

Keep the `--extra-index-url .../whl/cpu` line at the top of `requirements.txt`. It
installs the CPU build of PyTorch; without it pip pulls the ~2.5 GB CUDA build.

### Configuration (optional)

The defaults work for a local install (Qdrant on `localhost:6333`, Ollama on
`localhost:11434`, model `qwen3.5:4b`). To override anything, create `backend/.env`
with only the lines you need:

```ini
# Different model
MERCEK_LLM_MODEL=qwen3.5:9b

# Skip the Hugging Face version check on startup (after the first download)
MERCEK_HF_OFFLINE=true

# Use a GPU for embeddings
MERCEK_EMBED_DEVICE=cuda

# Remote OpenAI-compatible endpoint instead of local Ollama
MERCEK_LLM_OLLAMA_YEREL=false
MERCEK_LLM_BASE_URL=https://<provider>/v1
MERCEK_LLM_API_KEY=<key>
```

Settings are also read from `~/.mercek/mercek.env`, which takes precedence over
`backend/.env`. Put real API keys there, outside the repository. The full list of
settings with defaults is in [`backend/app/config.py`](backend/app/config.py).

### Load the knowledge base

```cmd
python -m app.knowledge.ingest
```

The first run downloads the BGE-M3 embedding model (~2.2 GB, 5-15 minutes, with
little console output). It ends by writing 37 entries to the `mercek_bilgi_tabani`
collection.

### Verify and run

```cmd
python -m app.dogrula
uvicorn app.main:app --reload
```

`app.dogrula` checks Python, packages, settings, Qdrant, the LLM, the embedding model
and an end-to-end search, and tells you what to run if something is missing. Every
line should read `[TAMAM]` (OK).

Check: http://localhost:8000/saglik (health) and http://localhost:8000/docs (Swagger).

---

## 5. Frontend

In a second terminal:

```cmd
cd C:\projects\mercek\frontend
npm install
npm run dev
```

Open http://localhost:5173.

---

## 6. First analysis

Upload a PDF or DOCX report. For a quick test, save the following as `test.txt` and
drop it on the page. Mercek is built for Turkish project reports, so the sample is in
Turkish (it describes symptom photos stored in Firebase, diagnoses in PostgreSQL,
summarisation via the OpenAI API and a sign-up form collecting name, birth date and
phone number).

```
3.1 Sistem Mimarisi
Kullanicilarin semptom fotograflari Firebase Realtime Database uzerinde saklanmaktadir.
Hasta teshis bilgileri PostgreSQL veritabanina yazilir ve gunluk olarak yedeklenir.
Metin ozetleme icin OpenAI API kullanilmaktadir.
Ilac hatirlatmalari FCM uzerinden anlik bildirim olarak gonderilir.

4.1 Kullanici Akisi
Kullanici kayit ekraninda ad, soyad, dogum tarihi ve telefon numarasi girer.
```

Deterministic findings appear within seconds; LLM findings follow in 3-6 minutes
with the 4B model on CPU.

---

## Daily use

On Windows, double-click **`baslat.bat`**. It starts Qdrant, the backend and the
frontend, then opens the browser. Manually:

```cmd
docker compose up -d qdrant
cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload
cd frontend && npm run dev
```

To stop: `Ctrl+C` in both terminals, then `docker compose stop qdrant`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Connection refused` from the backend | Qdrant is not running: `docker compose up -d qdrant` |
| Analysis stalls at the `getir` (retrieve) step | Knowledge base is empty: run `python -m app.knowledge.ingest` |
| Analysis fails at the `cikar` (extract) step | Ollama is unreachable, or `MERCEK_LLM_MODEL` does not match a name in `ollama list` |
| First analysis is slow to start | BGE-M3 is loading into memory (1-3 minutes, once per server start) |
| Very slow or the machine freezes | The model does not fit in RAM: use `qwen3.5:1.7b` |
| `pip install` downloads huge files | The CPU index line was removed from `requirements.txt`; restore it and run `pip cache purge` |
| `UnicodeEncodeError` in `cmd` | Run `chcp 65001` |
| Port already in use | `netstat -ano \| findstr :8000`, then `taskkill /PID <pid> /F` |

---

## Full ASVS corpus (optional)

The seed data includes 12 ASVS items. To load all 345 ASVS 5.0 requirements, from
`backend` with the virtual environment active:

```cmd
curl -L -o asvs.json https://github.com/OWASP/ASVS/releases/download/v5.0.0_release/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json
python -m app.knowledge.ingest --asvs asvs.json --sifirla
```

`--sifirla` (reset) rebuilds the collection. The seed ASVS items are dropped when the
full corpus is loaded, since they use 4.0.3 numbering. The downloaded file should be
~160 KB; if it is only a few KB, download it manually from the browser.
