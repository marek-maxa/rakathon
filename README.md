# MEDDI ONCO · Rakathon 2026

AI společník onkologického pacienta mezi kontrolami: vývoj obtíží,
vysvětlitelná triáž a srozumitelný další krok pro pacienta i zdravotnický tým.

Začínáme návrhem. Aplikace zatím není implementovaná. Nejdříve projdeme
datový balíček MEDDI a domluvíme jeden průchod od hlášení k výstupu.

## Soubory

| Kam | Co |
| --- | --- |
| [documents/](documents/README.md) | Aktivní podklady MEDDI a stav dostupnosti dat |
| [docs/challenge.md](docs/challenge.md) | Zadání a rozsah dema |
| [docs/architecture.md](docs/architecture.md) | Stack, rozhraní a spuštění projektu |
| [docs/tasks.md](docs/tasks.md) | Úkoly, vlastníci a stav |
| [docs/decisions.md](docs/decisions.md) | Důležitá rozhodnutí |
| [AGENTS.md](AGENTS.md) | Společné instrukce pro libovolné agenty |
| `pyproject.toml` + `uv.lock` | Knihovny a uzamčené verze |
| [docs/archive/](docs/archive/README.md), [documents/archive/](documents/archive/) | Historie výběru a podklady ostatních témat |

## Příkazy

Python 3.12 + uv, Linux i Windows PowerShell. Potřebujete Git a uv.

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

Zatím pouze vývojové nástroje pytest a Ruff. Knihovny pro aplikaci přidáme,
až je bude potřebovat konkrétní krok. Testy přibudou s implementací.

## Startovní prompt pro agenta

```text
Zorientuj se v repozitáři a řiď se společnými instrukcemi v AGENTS.md.
Přečti docs/challenge.md a docs/architecture.md. Čerpej z relevantních podkladů
v documents/; není potřeba načítat všechno.

Pracuj na domluveném kroku z docs/tasks.md. Zapiš se jako vlastník a nastav doing.
Respektuj úkoly ostatních. Ověř výsledek a aktualizuj stav na done nebo blocked.
Pokud krok ještě není domluvený nebo chybí zásadní informace, stručně to oznam.
Na závěr uveď, co je hotové, jak jsi to ověřil a co zbývá.
```
