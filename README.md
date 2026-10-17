# MEDDI ONCO · Rakathon 2026

AI společník onkologického pacienta mezi kontrolami: vývoj obtíží,
vysvětlitelná triáž a srozumitelný další krok pro pacienta i zdravotnický tým.

Implementované jsou LLM intake a společný backend triáže. Úplný průchod
s kartou, sledováním nálezů, doporučením a předáním týmu zbývá propojit.
[Aktuální plán pipeline a webu](docs/meddi-onco-plan.md) obsahuje zdrojované
požadavky a malé integrační kroky. Větev `web` zahrnuje aktuální backend z `main`
a zobrazuje barvu triáže, důvody a neúplnost posouzení.

## Soubory

| Kam | Co |
| --- | --- |
| [documents/](documents/README.md) | Aktivní podklady MEDDI a stav dostupnosti dat |
| [docs/challenge.md](docs/challenge.md) | Zadání a rozsah dema |
| [docs/meddi-onco-plan.md](docs/meddi-onco-plan.md) | Úplná revize požadavků, závislosti a plán začlenění do webu |
| [docs/architecture.md](docs/architecture.md) | Stack, rozhraní a spuštění projektu |
| [docs/tasks.md](docs/tasks.md) | Úkoly, vlastníci a stav |
| [docs/decisions.md](docs/decisions.md) | Důležitá rozhodnutí |
| [AGENTS.md](AGENTS.md) | Společné instrukce pro libovolné agenty |
| `pyproject.toml` + `uv.lock` | Knihovny a uzamčené verze |
| [rakathon_meddi_onco_data/](rakathon_meddi_onco_data/README.md) | Fiktivní pacienti, pravidla, dotazníky a oddělené reference |

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
| `uv run --locked python -m pytest -q` | Existující offline testy |
| `uv run --locked python main.py` | Strukturované porovnání s oddělenými referencemi |
| `git status --short` / `git diff` | Přehled změn |

Web používá Flask a HTML formuláře; JavaScript zobrazuje průběh zpracování
a brání opakovanému odeslání.

## Lokální webový průchod

Nastavte `MEDDI_LLM_API_KEY` lokálně v `llm_intake/.env` podle
`llm_intake/.env.example` a spusťte z kořene repozitáře:

```text
uv run python -m web.app
```

Otevřete `http://127.0.0.1:5000` a vyberte profil pacienta. Po úvodní otázce
následují cílená doptání a společná kontrola všech odpovědí s možností oprav.
Potvrzení přidá nový check-in do pracovní kopie `data/pacienti/<patient_id>.json`;
nevyřešené odpovědi zůstávají bez přiřazené hodnoty. Rozpracovaný stav je pouze
v paměti procesu. Pracovní kopie zachovává původní kontext a historii pacienta;
zdrojový balíček se nemění. Report dostupný z odkazu u profilu zahrnuje i nové
uložené odpovědi. Po zpracování odpovědi a při závěrečném potvrzení se volá
společný backend triáže. Formulář i report zobrazují barvu, důvody a neúplnost;
potvrzený check-in uchovává také vyhodnocení s celým původním kontaktem.
Jde o prototyp s omezeným pokrytím, nikoli klinicky ověřený systém.

Výpočetní backend nemá vlastní runtime závislosti; testy používají pytest a Ruff. Kontrakt
a syntetický CLI průchod popisuje [docs/backend.md](docs/backend.md).
LLM konfigurace a použití jsou v [llm_intake/README.md](llm_intake/README.md).
Webové knihovny jsou již zahrnuté v manifestu a locku větve web.

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
