# MEDDI ONCO

Prototyp podpory onkologického pacienta mezi kontrolami: sběr obtíží,
vysvětlitelná triáž a další krok pro pacienta i zdravotnický tým.

Funguje MASTER rozhovor s cíleným doptáním, společným potvrzením, uložením
kontaktu a historickým reportem. Aktivní karta, plánované kontroly a přeměření,
předání týmu a odborné souhrny zbývají propojit. Stav jednotlivých částí je
v [architektuře](docs/architecture.md#implementovaný-stav).

## Spuštění webu

Python 3.12 + uv; příkazy spouštějte z kořene repozitáře na Linuxu
nebo ve Windows PowerShellu.

```text
uv sync --locked
```

Zkopírujte [llm_intake/.env.example](llm_intake/.env.example) do
`llm_intake/.env` a lokálně nastavte `MEDDI_LLM_API_KEY`. Potom:

```text
uv run --locked python -m web.app
```

Otevřete http://127.0.0.1:5000 a vyberte syntetický profil. Web načítá `.env`
automaticky; potvrzené kontakty zapisuje do `data/pacienti/`. Rozpracovaný
rozhovor je pouze v paměti. Podrobnosti konfigurace a další příkazy jsou
v [architektuře](docs/architecture.md#spuštění-a-kontroly).

## Dokumentace

| Dokument | Odpovědnost |
| --- | --- |
| [Zadání](docs/challenge.md) | Požadavky pořadatele, zdroje a hranice řešení |
| [Architektura](docs/architecture.md) | Implementovaný stav, moduly, ukládání, spuštění a kontroly |
| [Backend](docs/backend.md) | Kontrakt triáže, čas, validace, pokrytí a klinické mezery |
| [Plán](docs/meddi-onco-plan.md) | Cílový tok, karta, kontroly, rozhraní a podmínky dokončení |
| [Úkoly](docs/tasks.md) | Otevřená práce, pořadí a vlastníci |
| [Rozhodnutí](docs/decisions.md) | Platné technické volby a nevyřešené konflikty |
| [LLM intake](llm_intake/README.md) | Konfigurace a použití modulu; odkaz na jeho datový kontrakt |
| [Notifikace](notifications/README.md) | Samostatné SMTP demo a jeho omezení |
| [Podklady](documents/README.md) | Původní zadání a datový balíček pořadatele |
| [AGENTS.md](AGENTS.md) | Instrukce pro práci v repozitáři |

Pracujte se syntetickými nebo schválenými daty. Klíče a skutečné pacientské
údaje nepatří do Gitu. Reference slouží pouze k oddělenému vyhodnocení;
prototyp není klinicky schválený systém.
