# Rakathon 2026

Python 3.12 + uv. Linux i Windows PowerShell.

## Soubory

| Kam | Co |
| --- | --- |
| [documents/](documents/README.md) | Sem nahrajte podklady organizátorů, PDF, prezentace a tipy. Agenti tu hledají relevantní zdroje. |
| [docs/challenge.md](docs/challenge.md) | Zadání a rozsah dema |
| [docs/architecture.md](docs/architecture.md) | Stack, rozhraní a spuštění projektu |
| [docs/tasks.md](docs/tasks.md) | Úkoly, vlastníci a stav |
| [docs/decisions.md](docs/decisions.md) | Důležitá rozhodnutí |
| [AGENTS.md](AGENTS.md) | Společné instrukce pro libovolné agenty |
| `pyproject.toml` + `uv.lock` | Knihovny a uzamčené verze |

## Příkazy

Potřebujete [Git](https://git-scm.com/downloads) a [uv](https://docs.astral.sh/uv/getting-started/installation/).

```text
git clone https://github.com/marek-maxa/rakathon.git
cd rakathon
uv sync --locked
```

| Příkaz | Účel |
| --- | --- |
| `uv sync --locked` | Instalace / synchronizace prostředí |
| `uv run python cesta/skript.py` | Spuštění vlastního Python skriptu |
| `uv add NAZEV` / `uv add --dev NAZEV` | Přidání knihovny / vývojového nástroje |
| `uv run ruff check .` | Lint |
| `uv run pytest` | Testy, až je přidáme |
| `git status --short` / `git diff` | Přehled změn |

Nainstalováno: NumPy, pandas, scikit-learn, matplotlib, HTTPX, python-dotenv, pytest, Ruff.

## Startovní prompt pro agenta

```text
Zorientuj se v repozitáři a řiď se společnými instrukcemi v AGENTS.md.
Přečti docs/challenge.md a docs/architecture.md. Čerpej z relevantních podkladů
v documents/; není potřeba načítat všechno.

Pracuj podle docs/tasks.md: pokračuj ve svém rozpracovaném úkolu, jinak vezmi
první volný úkol todo. Zapiš se jako vlastník a nastav doing. Respektuj úkoly
ostatních. Postupuj samostatně, ověř výsledek a aktualizuj stav na done nebo blocked.
Pokud není žádný připravený úkol nebo chybí zásadní informace, stručně to oznam.
Na závěr uveď, co je hotové, jak jsi to ověřil a co zbývá.
```
