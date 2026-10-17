# Úkoly MEDDI ONCO

Stavy: `todo`, `doing`, `blocked`, `done`. Jeden vlastník na úkol.
Implementační kroky zahajujeme po společné domluvě, postupně.

| Úkol / rozsah souborů | Vlastník | Stav | Hotovo, když |
| --- | --- | --- | --- |
| Připravit a nasadit současný Flask demo web na Azure; scripts/package_azure.py, pyproject.toml, uv.lock, docs/ | Aktuální relace / main | done | ZIP bez tajemství a referencí, lokální testy, nastavený Gunicorn, úspěšný Azure build a ověřené vzdálené přihlášení, formulář, statika i report |
| Doplnit MEDDI_LLM_API_KEY v Azure a ověřit syntetickou odpověď | Tým | todo | Klíč nastavený přes Azure Portal bez sdílení v chatu; potvrzený průchod LLM formulářem. Klíč při nasazení nebyl lokálně ani v Azure dostupný |
| Ochrana webu HTTP Basic Auth; web/app.py, tests/test_web_auth.py, llm_intake/.env.example, docs/ | Aktuální relace / main | done | Všechny cesty chráněné, chybějící konfigurace odmítne přístup, ověřené chybné i správné údaje; zdokumentované Azure proměnné a HTTPS. Vzdálené nastavení a nasazení ještě neprovedeno |
| Nový začátek pro MEDDI; README.md, AGENTS.md, docs/, documents/, pyproject.toml, uv.lock a lokální cache | Aktuální relace / main | done | Zdrojované zadání, plán a archiv; odstraněné duplicity, cache a nepotřebné závislosti; ověřené odkazy, integrita podkladů a prostředí |
| Zhodnotit představu týmu a zpřesnit návrh; docs/architecture.md, docs/decisions.md, docs/tasks.md, docs/challenge.md, README.md, documents/README.md | Aktuální relace / main | done | Zapsaný CLI proof of concept, karta a role LLM; doporučení odlišená od rozhodnutí; tým potvrdil simulovaný čas, zaznamenané odpovědi a dodaná data |
| Dohledat MEDDI JSON, pravidla a popis výstupu; docs/challenge.md, documents/README.md | Aktuální relace / main | done | Otevřená ukázka; lokálně 14 pacientů / 171 check-inů, přečtené README a pravidla; výstup se páruje přes checkin_id |
| Samostatný modul extrakce a potvrzení; llm_intake/, tests/__init__.py, tests/test_llm_intake.py, docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | Výběr modelu podložen dokumentací; pevné otázky, extrakce do validovaného JSON, pacientovo potvrzení a oprava; CLI a Python rozhraní a testy bez sítě; API adaptér oddělený, živé připojení ověřuje navazující úkol |
| Opravit 401 a upřesnit slovní sběr; llm_intake/, tests/test_llm_intake.py, docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | Ověřená autentizace api-key a deployment gpt-6-1-sol-dz-eu; pacient vidí otázku a slovní návrh, možnosti a barvy zůstávají interní; volba se deterministicky mapuje na metadata z definic |
| Cílené doptání při nejasné odpovědi; llm_intake/, tests/test_llm_intake.py, docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | LLM naváže konkrétní otázkou na chybějící rozlišení možností; zachová kontext otázek a odpovědí, omezený počet doptání, měřitelné počty tahů; bez nuceného výběru a bez nové RAG infrastruktury |
| Samostatné vyhodnocení přiřazení a nutnosti doptání; llm_intake/ | Nepřiřazeno | todo | Označené případy oddělené od promptových příkladů, přímé i nejasné odpovědi, negace, opravy a slovenština; správnost volby, zbytečná doptání, počet tahů a nevyřešené relace mají jmenovatele; případný práh podobnosti teprve podle výsledků |
| Živé ověření LLM brány se syntetickými odpověďmi; llm_intake/ | Aktuální relace / main | done | Lokální klíč, deployment a autentizace ověřeny; striktní schéma přijato; počáteční odpověď, negace v opravě a nejasnost ověřeny skutečným LLM. Klíč do Gitu ani chatu nepatří |
| Zapsat rozhodnutí o triáži v kódu; docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | Extrakce LLM oddělená od veškeré triáže, odstraněná varianta návrhu úrovně modelem; ověřeno čtením změn a git diff --check |
| Malá deterministická triáž; triage.py, docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | Jeden soubor přijímá JSON, vrací barvu s důvody a nejistotou; ověřené hranice, priority pravidel a chybné vstupy; připraveno k review |
| Sloučit dokumentaci triáže a LLM intake před commitem; docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | Zachované obě implementace a historie rozhodnutí, sjednocený popis aktuálního stavu; 59 testů a Ruff prošly |
| Minimálně propojit potvrzený intake s triáží; triage.py, llm_intake/__main__.py, tests/test_triage_intake.py, docs/ | Aktuální relace / main | done | CLI po potvrzení vypíše barvu či neurčeno; mapuje pocit a NRS, neodvozuje chybějící fakta; 65 testů a Ruff prošly |
| Vícekrokový formulář propojený s backendem; web/, llm_intake/core.py, tests/test_web.py, docs/, README.md, pyproject.toml, uv.lock | Aktuální relace / main | done | Nechat chatové bubliny mimo rozhraní; serverové formuláře, potvrzení/upravení výběru, doptání, pokračování bez přiřazení a chyby zřetelně oddělené od formuláře |
| S mentorem potvrdit nejasnosti pravidel a časových údajů; docs/challenge.md, docs/architecture.md | Tým + mentor | todo | Známá dostupnost údajů v čase, vyřešené interpretační otázky, případné dodatečné hodnoticí rozhraní, termín a způsob odevzdání |
| Společně projít jeden případ a domluvit schéma extrakce a karty; docs/architecture.md | Tým | todo | Definovaná pozorování se zdrojem a časem, jejich použití v pravidlech a výstupy pro pacienta i zdravotníka; zvolený nejmenší implementační krok |
| První průchod načtení → triáž → výstup | Nepřiřazeno | todo | Po domluvě předchozího kroku konkretizovat soubory; jeden případ běží s dohledatelnými důvody a bez budoucích dat či referencí ve vstupu |
| Vyhodnocení všech šesti povinných situací a hraničních vstupů | Nepřiřazeno | todo | Časové přehrávání, podhodnocení závažnosti a zbytečné poplachy mají ověřitelné výsledky; klinickou interpretaci prošel mentor |
| Demo pro pacienta a tým, návrh integrace | Nepřiřazeno | todo | Srozumitelný další krok, souhrn a simulované upozornění; opakovatelný scénář i záloha bez externí služby |

Ověření úklidu 16. 10. 2026: `uv sync --locked --offline` a
`uv run --locked ruff check --no-cache .` prošly. SHA-256 potvrdily nezměněný
obsah 40 primárních podkladů (38 v archivu, 2 MEDDI); tři odstraněné kopie měly
shodný zachovaný originál. Ověřeno 23 místních Markdown odkazů a `git diff --check`.
`uv run --locked pytest -p no:cacheprovider` nenašel testy (kód 5), aplikace ještě
neexistuje. Kontroly proběhly na Linuxu s Pythonem 3.12.15, Windows se nespouštěl.
Při úklidu MEDDI JSON chyběl; nyní je dostupný v `rakathon_meddi_onco_data/`.
Zbývá společná domluva dalšího kroku a upřesnění s mentorem.

Zpřesnění návrhu 16. 10. 2026: přečtené README dat, pravidla a pacientská cesta,
lokálně načtené JSON a prohlédnutá struktura jednoho pacienta. Nešlo o úplný
datový audit ani o ověření klinické správnosti. Měněna pouze dokumentace;
provedeno `git diff --check` a kontrola místních odkazů, aplikační testy neběžely.
Opraveny také zastaralé odkazy na archiv, který už v aktuálním checkoutu není.

První implementace triáže 16. 10. 2026: `triage.py` bez nových závislostí.
Přes `uv run --locked python` prošlo 50 samostatných kontrol funkce a CLI
na macOS v Pythonu 3.12.15: čtyři barvy, teplota 37,99/38 °C,
SpO2 89,99/90/91,99/92 %, hranice NRS, souběh pravidel, nezměněný vstup,
chybějící údaje, neplatné typy a rozsahy, NaN/nekonečno, poškozený JSON,
UTF-8 BOM a chybějící soubor. Šlo o jednorázové kontroly, nikoli uloženou
testovací sadu pytest. Ruff check, Ruff format --check a git diff --check
prošly. Windows se nespouštěl; klinická správnost nebyla ověřena mentorem.
Zbývá týmové review, rozšíření pravidel a pozdější napojení LLM.

Úprava čitelnosti `triage.py` 16. 10. 2026: anglické názvy funkcí, proměnných,
JSON polí, barev, komentářů i zpráv; explicitní větvení při výběru výsledné
barvy. Aktuální kontrakt je v architecture.md, staré české klíče se nepřijímají.
Hotovo: 23 jednorázových kontrol funkce a CLI v Pythonu 3.12 prošlo,
stejně jako Ruff check, format --check a git diff --check. Rozsah pravidel
zůstává omezený; klinické ověření a týmové review jsou nadále otevřené.

Zjednodušení na pokyn týmu: odstraněn vlastní validátor, TypedDict a try/except
z triage.py. Vstup se předpokládá připravený; běžné chyby hlásí přímo Python.
Zachována práce s chybějícími údaji a pravidla posouzení. Dokumentace rozhraní
upravena; předchozí záznamy kontrol popisují tehdejší verze s validátorem.
Po zjednodušení prošlo 7 kontrol barev a neúplných vstupů v Pythonu 3.12,
Ruff check a git diff --check.

Rozdělení triáže na pokyn týmu: čtyři malé funkce vracejí skóre 1–4 nebo
None; evaluate_triage bere maximum známých skóre. Výstup zjednodušen na
color, scores a requires_review; aktuální rozhraní je v architecture.md.
Hotovo: 20 kontrol jednotlivých kritérií a agregace v Pythonu 3.12,
Ruff check, format --check a git diff --check prošly.

Na pokyn týmu doplněn Severity(IntEnum) místo čísel v pravidlech; jednotlivé
funkce mají anglický popis a odkaz na konkrétní oddíl pravidla. Agregace
nadále používá max a JSON zachovává číselná skóre.
Ověřeno 11 kontrolami enumu, pravidel, agregace a JSON serializace v Pythonu
3.12; Ruff check, format --check a git diff --check prošly.

LLM intake 16. 10. 2026: `uv run --locked python -m pytest -q` — 40 testů prošlo;
`uv run --locked ruff check .` a `git diff --check` prošly. Ověřen běh CLI `--list`,
místní odkazy, osm syntetických příkladů a ignorování `llm_intake/.env` Gitem.
Testy nahrazují model i HTTP transport. `MEDDI_LLM_API_KEY` nebyl v prostředí
nastaven, skutečná dostupnost brány, autentizace, deployment a kvalita extrakce
proto nejsou ověřené. `pyproject.toml`, `uv.lock` ani zdrojová data se neměnily.

Oprava připojení a upřesnění průchodu 16. 10. 2026: 401 reprodukováno,
hlavička `api-key` opravila autentizaci. Po dodání deploymentu
`gpt-6-1-sol-dz-eu` prošla živá extrakce, odmítnutí a oprava (index 0 → 1),
potvrzení i samostatná nejasná odpověď (`needs_answer`, žádná domyšlená hodnota).
Šlo pouze o syntetické zprávy, nikoli benchmark nebo klinické ověření.
`uv run --locked python -m pytest -q` — 48 testů prošlo; Ruff a
`git diff --check` prošly, místní odkazy ověřeny. Lokální `.env` má opravený
deployment a hlavičku, klíč zachován; soubor je ignorovaný Gitem.

Cílené doptání 16. 10. 2026: 59 testů prošlo (`uv run --locked python -m pytest -q`),
Ruff, `git diff --check` a místní odkazy prošly. Skutečný LLM na syntetickém
„ne, nejde mi spat“ položil otázku na odpočinek bez spánku. Ve scénáři s úplnějším
doplněním stačilo jedno doptání; s krátkými odpověďmi následovalo druhé na omezení
aktivit a pak potvrditelná možnost index 1. Ověřeno uchování kontextu otázek.
Nejde o obecný benchmark. Export je nyní v2, extraktor přijímá třetí argument
`source_questions`; limity, opakování otázky a nemožnost nuceně potvrdit nevyřešenou
odpověď ověřují automatické testy. Závislosti ani zdrojová data se neměnily.

Úprava webu podle zpětné vazby 16. 10. 2026: chatové bubliny nahrazeny
jednoduchým formulářem s jednou otázkou a číslováním kroků. Chyba API nebo
validace se zobrazí jako samostatné výrazné upozornění; nepoužívaný chatový
skript odstraněn. `uv run --locked pytest -q` — 71 testů prošlo;
`uv run --locked ruff check .` a `git diff --check` prošly.

Sloučení před commitem 16. 10. 2026: začleněn commit `6f0d09e` z `origin/main`
a zachovány lokální změny LLM intake. Konflikty ve třech týmových dokumentech
vyřešeny se zachováním obou modulů; jejich propojení zůstává dalším krokem.
`uv run --locked python -m pytest -q`: 59 testů prošlo;
`uv run --locked ruff check .` prošel. Kontroly proběhly na Linuxu,
bez živého volání LLM a bez nového klinického ověření.

Automatické načtení webového `.env` 16. 10. 2026: web při importu načte
`llm_intake/.env` přes `python-dotenv`; existující proměnné prostředí nepřepisuje.
Spuštění webu už nevyžaduje `uv --env-file`. Ověřeno po odstranění klíče z
procesního prostředí, bez jeho výpisu: import webu načetl lokální hodnotu.
`uv run --locked pytest -q` — 71 testů prošlo; Ruff a `git diff --check`
prošly. Živé volání LLM nebylo součástí kontroly.

Rozřešení konfliktů webu 17. 10. 2026: zachovány výběr profilu a reportový
blueprint ve stejné Flask aplikaci; formulář používá dostupný `llm_intake.Intake`.
Alternativní `MasterDialogue` odkazoval na moduly, které v tomto checkoutu
neexistují, proto tento tok nelze bezpečně sloučit bez přidání jeho implementace.
`uv run --locked pytest -q` — 81 testů prošlo; Ruff, `git diff --check` a kontrola
konfliktních značek prošly. Žádný commit vytvořen.

Ochrana webu heslem 17. 10. 2026: HTTP Basic Auth před všemi Flask cestami,
včetně blueprintu reportů, statických souborů a POST. Chybějící konfigurace
vrací 503, chybné či chybějící údaje 401; UTF-8 porovnání používá
secrets.compare_digest. Bez nových závislostí. Doplněn příklad prostředí,
architektura a rozhodnutí. Na Windows / Python 3.12.12 prošlo
`uv run --cache-dir .scratch/uv-cache --offline --locked pytest -q -p no:cacheprovider`
(94 testů, z toho 27 pro autentizaci), Ruff check celého projektu,
Ruff format --check obou změněných Python souborů a git diff --check.
Závislosti byly nejprve doplněny přes uv sync --locked s pracovní cache.
Bez živého LLM, commitu či nasazení. V Azure zbývá nastavit obě proměnné,
zapnout HTTPS Only a nasadit kód; skutečné přihlašovací údaje nebyly vytvořeny.

Azure demo 17. 10. 2026: přes uv doplněn Gunicorn pouze mimo Windows,
pyproject.toml a uv.lock aktualizovány společně. scripts/package_azure.py
vytváří dist/meddi-azure.zip (35 souborů) bez .env, ground_truth a vývojových
souborů. ZIP integrita i vyloučení ověřeny; rozbalený balíček prošel kontrolou
formuláře, statiky, reportu a autentizace. 94 pytest testů, Ruff check celého
projektu, format --check balicího skriptu a git diff --check prošly na Windows.
Azure OneDeploy c6cc9134-5dc5-4fab-beb1-1cb70dbb4f05: build úspěšný (status 4).
Na veřejné HTTPS adrese ověřeno bez hesla 401, se správnými údaji 200 pro
/, /static/style.css a /patients/ONC-004/report. Nebylo voláno LLM.
Nastaveny build, startup, stabilní Flask secret a neklíčové LLM proměnné.
Existující Basic Auth údaje i HTTPS Only zůstaly zachované. Zbývá týmové
zadání MEDDI_LLM_API_KEY do Azure Portalu a ověření LLM formuláře.
Nové nezapojené moduly od týmu byly zachovány beze změn. Bez commitu/pushe.
