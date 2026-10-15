# Rakathon 2026 — rychlý návod

**Vývoj: 16. 10. 2026 12:00 → 17. 10. 2026 12:00 CEST.**
[Oficiální program](https://www.rakathon.cz/) zahrnuje i další části akce do neděle.
Výzvu a aplikační stack vybereme na místě. Zatím je připravené jen pracovní prostředí.

## 1. Před začátkem Rakathonu

**Linux / Windows přes WSL2.** Nástroje používají Bash a linuxové cesty; nativní
PowerShell/CMD není podporovaný a Git Bash není ověřený. Testy běžely na Linuxu;
WSL2 zde nebylo možné otestovat.

Na Windows otevři PowerShell jako správce a podle
[návodu Microsoftu](https://learn.microsoft.com/en-us/windows/wsl/install) spusť:

```powershell
wsl --install -d Ubuntu
```

Po případném restartu otevři Ubuntu a dokonči vytvoření uživatele. Dál pracuj
**v terminálu Ubuntu**: Git, [uv](https://docs.astral.sh/uv/getting-started/installation/),
Python ≥ 3.11 i používané AI CLI (`codex`, `claude`, `agy`) instaluj uvnitř WSL.
Repo klonuj do linuxového domovského adresáře (`~/projekty`), nikoli do `/mnt/c`;
nesdílej `.venv` mezi Windows a WSL. Pro VS Code je volitelně potřeba
[rozšíření WSL](https://code.visualstudio.com/docs/remote/wsl), potom otevři repo
příkazem `code .` z Ubuntu. Rozšíření ani systémové nástroje tento repo setup neinstaluje.

**Po naklonování — Linux i Ubuntu/WSL.** Potřebuješ Git, Bash, `uv` a Python ≥ 3.11.
Používané AI CLI nainstaluj podle [oficiálních návodů](docs/usage-playbook.md#command-reference);
VS Code (`code`) a ShellCheck jsou volitelné. Pokud chybí Python, stačí
`uv python install 3.12` (jednorázově stáhne interpreter). Zvol vlastní pracovní adresář:

```bash
mkdir -p ~/projekty
cd ~/projekty
git clone https://github.com/marek-maxa/rakathon.git
cd rakathon
uv sync --offline
uv run ./rak check
uv run ./rak status
```

`uv` vytvoří lokální `.venv`; nemusíš ji aktivovat. Pomocné nástroje nemají žádné
externí Python závislosti a neurčují stack výsledné aplikace. `check` prověří
prostředí a otestuje pracovní nástroje, nikoli budoucí aplikaci.
`FAILURE` oprav; `WARNING` a `UNVERIFIED` si přečti. Při problému s `uv` lze diagnostiku
spustit přímo: `bash scripts/doctor.sh`.

**Proč `./rak`?** Je to přímá cesta k místnímu skriptu. `uv run rak` by hledalo
příkaz na `PATH`; museli bychom nástroj balit a instalovat jako konzolový příkaz.
Současná varianta proto nepotřebuje build backend ani další závislosti.
Viz [pravidla uv pro konzolové příkazy](https://docs.astral.sh/uv/concepts/projects/config/#command-line-interfaces).

**Ověř účty a kapacitu.** Použij přihlášení k ChatGPT Plus, Claude Pro a osobnímu
Google účtu pro Antigravity. Nespouštěj placené API ani kreditové overages.

| Nástroj | Kontrola využití | Kontrola instrukcí |
| --- | --- | --- |
| Codex | `/status` | načítá `AGENTS.md` přímo |
| Claude Code | `/usage` | `/memory` — `CLAUDE.md` importuje `AGENTS.md` |
| Antigravity (`agy`) | `/usage` nebo `/quota` | `/context`, `/rules` — načítá `AGENTS.md` přímo |

Google AI Plus má v Antigravity týdenní základní kvótu; nepočítej s výhodami AI Pro.
Aktuální zůstatky a reset ověř v účtu. [Strategie použití modelů a limity](docs/usage-playbook.md).

**Určete člověka pro integraci do `main`.** První commit je potřeba jen při zakládání
prázdného repozitáře; po běžném klonování už existuje a následující blok přeskoč.
Správce prázdného repozitáře po kontrole souborů provede:

```bash
git status --short
git add AGENTS.md CLAUDE.md .gitignore .gitattributes .vscode/settings.json README.md \
  pyproject.toml uv.lock rak scripts/ tests/ docs/
git diff --cached --check
git diff --cached
git commit -m "chore: prepare Rakathon workspace"
```

Ověřte týmový remote a větve (`git remote -v`, `git branch -vv`); nástroj počítá
s větví `main`. Správce musí úvodní soubory také ručně pushnout, než je ostatní mohou
klonovat. Nic se automaticky nepushuje ani nesynchronizuje.

## 2. Po startu: vyberte zadání a rozdělte práci

1. Do [challenge.md](docs/challenge.md) zapište požadavky, kritéria hodnocení,
   povolená data a způsob odevzdání. Vyberte jednu hlavní demo cestu.
2. Do [architecture.md](docs/architecture.md) zapište stack, rozhraní a skutečné
   příkazy pro instalaci, běh aplikace a testy. Tyto příkazy jsou zatím **TBD**.
3. V [tasks.md](docs/tasks.md) rozdělte malé úkoly: jeden vlastník, konkrétní soubory,
   závislosti a ověřitelný výsledek. Integrátor koordinuje změny sdílených souborů.
4. Integrátor schválené zadání a rozhraní commitne do `main`, aby je nové worktrees převzaly.

## 3. Běžný pracovní cyklus

**Založ úkol z čistého hlavního checkoutu na větvi `main`:**

```bash
uv run ./rak task data-contract --open
cd .worktrees/data-contract
uv run ./rak agent codex
```

`task` vytvoří větev `task/data-contract` a samostatný Git worktree; `--open`
otevře nové okno VS Code. Název nahraď skutečným úkolem. Příkaz nemění adresář
tvého terminálu, proto je potřeba `cd`. V integrovaném terminálu nového okna už jsi
v task worktree. V něm `uv` při prvním použití vytvoří vlastní `.venv`.

Místo `codex` lze zvolit `claude` nebo `agy`. Spustí se **jen vybraný nástroj**,
v task checkoutu, s jeho běžnými oprávněními a přihlášením. Pomocný příkaz odmítne
spustit zapisujícího agenta na `main`. Jeden checkout = jeden samostatný zapisující
agent; dalšímu založ jiný úkol/worktree. Před zadáním promptu ověř vlastníka a rozsah.

**Při práci a před předáním:**

```bash
uv run ./rak status
# Spusť také testy aplikace uvedené v docs/architecture.md.
git diff --check
git diff
```

Po kontrole commitni pouze soubory svého úkolu (`git add konkretni/soubor`, potom
`git commit -m "feat: ..."`). Při předání uveď výsledek, skutečně spuštěné testy a
zbývající problém; stačí [krátký handoff](docs/handoff-template.md). `check` spouštěj
při změnách pracovních nástrojů; aplikační testy vybírej podle konkrétní změny.

**Integrátor** zkontroluje diff, ručně začlení změny do `main` a otestuje celek.
Aktualizace větví, merge a bezpečné odstranění worktree mají
[samostatný návod](docs/git-workflow.md). Nástroj je automaticky neprovádí.

## Tahák příkazů

Vždy z kořene příslušného checkoutu; možnosti zobrazí `uv run ./rak --help`.

| Příkaz | Co udělá |
| --- | --- |
| `uv run ./rak doctor` | Lokální kontrola nástrojů a připravenosti |
| `uv run ./rak status` | Git stav, worktrees, úkoly a kde zjistit kvóty |
| `uv run ./rak check` | Doctor + testy pracovních nástrojů bez volání AI |
| `uv run ./rak task NAZEV --open` | Nová task větev/worktree z čistého `main`, volitelně VS Code |
| `uv run ./rak agent codex` | Codex v aktuálním task checkoutu |
| `uv run ./rak agent claude` | Claude Code v aktuálním task checkoutu |
| `uv run ./rak agent agy` | Antigravity v aktuálním task checkoutu |

Používej syntetická nebo výslovně schválená data. Pacientské údaje a přístupové
klíče nepatří do Git historie ani do promptů bez odpovídajícího oprávnění.
`.gitignore` nechrání před odesláním dat. Klinické závěry AI musí ověřit člověk.
Pravidla agentů jsou jen v [AGENTS.md](AGENTS.md); důležité volby zapisujte stručně
do [decisions.md](docs/decisions.md).
