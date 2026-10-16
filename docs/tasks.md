# Úkoly MEDDI ONCO

Stavy: `todo`, `doing`, `blocked`, `done`. Jeden vlastník na úkol.
Implementační kroky zahajujeme po společné domluvě, postupně.

| Úkol / rozsah souborů | Vlastník | Stav | Hotovo, když |
| --- | --- | --- | --- |
| Porovnat a sloučit pipeline adaptér s d1b58f4; docs/, triage.py, llm_intake/__init__.py, tests/ | Aktuální relace / main | done | Obnovená historie LLM, zachované nové jádro a veřejná API, zdůvodněné rozdíly v merge-review.md, opravená záměna délky za teplotu; 502 testů a Ruff prošly |
| Ověřit efektivitu a přesnost LLM; client.py, master.py, dialogue.py, evaluate_topics.py, testy a docs/ | Aktuální relace / main | done | Skutečné API měření: MASTER −28,2 % a cílená únava −56,1 % vstupních tokenů; zachovaná sémantika všech 49 otázek. Konečná varianta 68/68 živých případů, 74/74 očekávaných témat, 0 nepovolených přiřazení v 15 přísně označených případech; 9 cílených scénářů a 260 automatických testů prošlo. Objevená regrese filtru brány opravena, podrobnosti níže |
| Úplné směrování témat MASTER; llm_intake/question_topics.json, question_catalog.py, master_contract.py, master.py, master_schema.json, master_prompt.md, dialogue.py, evaluate_topics.py, testy a docs/ | Aktuální relace / main | done | 49/49 otázek má klíčová slova, kontext a přesné ID; celý katalog v promptu, enum ve schématu, mechanické párování a zachované odložené otázky. 250 testů a Ruff prošly; 53 živých syntetických případů zachytilo 55/55 očekávaných témat, omezené požadavky opakovány pomaleji; podrobnosti níže |
| Sanity check, pull a sloučení před publikací; docs/, llm_intake/, tests/ | Aktuální relace / main | done | Začleněn origin/main 7b6e26f, zachovány obě strany dokumentace a CLI; 159 testů, Ruff, MASTER CLI bez varování a 36 místních odkazů prošlo |
| Review LLM, balíček otázky, větvení a výstup pipeline; llm_intake/, tests/, docs/ | Aktuální relace / main | done | Sdílený balíček, 13 příkladů bez kopií definic, QuestionnaireFlow, /moznosti, pipeline paket a diagram; 116 testů, Ruff a dvě živé syntetické extrakce prošly. MASTER extraktor, triáž a karta zůstávají oddělené |
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
| Návrh MASTER QUESTION a propojení; docs/master-question.md, docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | Prověřené aktuální moduly a podklady; zdrojované mezery, tok zprávy/faktů/otázek/karty, konzervativní triáž bez falšování faktů, limity zátěže a malé implementační kroky; zatím jen návrh bez změny běžícího API |
| Minimální LLM kontrakt faktů a první katalog; llm_intake/master_contract.py, llm_intake/question_catalog.py, llm_intake/master_examples.json, llm_intake/MASTER_CONTRACT.md, tests/test_master_contract.py, docs/ | Aktuální relace / main | done | Samostatný formát zprávy a faktů se zdrojem, časovým textem a nejistotou; 49 dvojic ID a první vazby šesti témat, pět syntetických příkladů; 86 testů a Ruff prošly, bez zásahů do triáže, karty a intake v2 |
| Extraktor MASTER QUESTION nad připraveným kontraktem; llm_intake/master.py, master_prompt.md, master_schema.json, client.py, ukázkové JSON, tests/test_master_extraction.py a docs/ | Aktuální relace / main | done | Striktní extrakce s pěti příklady a sdíleným transportem, kandidáti a nepokryté pojmy, CLI nad zaznamenanou zprávou; 149 testů a tři živé syntetické scénáře prošly. Bez triáže, karty a automatického rozhovoru |
| Napojit kandidáty MASTER na omezený dialog a potvrzování; llm_intake/dialogue.py, core.py, client.py, flow.py, pipeline.py, prompt.md, tests/test_master_dialogue.py a docs/ | Aktuální relace / main | done | Interaktivní MASTER i vstup ze souboru, původní otázky a zdroje, potvrzení/oprava, nová témata a podmíněné větve, rozpočet včetně potvrzení a JSON; 183 testů, Ruff a dva živé syntetické CLI průchody prošly; cílené CLI a triáž zachované |
| Vyhodnotit celý MASTER dialog; llm_intake/ a oddělené evaluační příklady | Nepřiřazeno | todo | Katalog všech otázek a samostatná regrese rozpoznání témat už existují; zbývají nezávislé scénáře správnosti potvrzené možnosti, počtu dotazů, rozporů a nevyřešených kontaktů. Samostatně klinická integrace a pravidla |
| Domluvit budoucí napojení LLM faktů na pravidla a kartu; docs/master-question.md, docs/architecture.md | Tým | todo | Mapování k triage.py, pokrytí tvrdých pravidel, rozpočet kontaktu a práce s nejistotou; vyjasněné mezery hranic průjmu a NRS. Samostatná práce LLM části tím není blokovaná |
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

Sloučení před commitem 16. 10. 2026: začleněn commit `6f0d09e` z `origin/main`
a zachovány lokální změny LLM intake. Konflikty ve třech týmových dokumentech
vyřešeny se zachováním obou modulů; jejich propojení zůstává dalším krokem.
`uv run --locked python -m pytest -q`: 59 testů prošlo;
`uv run --locked ruff check .` prošel. Kontroly proběhly na Linuxu,
bez živého volání LLM a bez nového klinického ověření.

Návrh MASTER QUESTION 16. 10. 2026: přečteny aktuální `triage.py`, intake v2,
README balíčku, pravidla a pacientská cesta; ověřeny definice 4 dotazníků /
49 otázek a relevantní zprávy dvou fiktivních pacientů, bez ground truth.
Zapsáno propojení, skutečné mezery a zdroje v `docs/master-question.md`.
Stávajících 59 testů prošlo. Mění se pouze dokumentace; žádná nová orchestrace,
RAG, karta, časování ani vyhodnocení alternativ nebyly implementované nebo
klinicky ověřené. Provedeno `git diff --check` a kontrola místních odkazů.

První LLM kontrakt MASTER QUESTION 16. 10. 2026: přidané samostatné typy zprávy,
faktu a číselného rozsahu, paket se zdrojem a nepotvrzeným stavem, katalog
49 dvojic ID s prvními vazbami šesti témat a pět ručních syntetických příkladů.
`uv run --locked python -m pytest -q`: 86 testů prošlo (27 nových);
`uv run --locked ruff check .`, kontrola formátu nových Python souborů,
`git diff --check` a místní odkazy prošly. Linux / Python 3.12;
Windows se nespouštěl. Bez živého LLM volání nebo měření kvality extrakce;
extraktor nad MASTER QUESTION ještě neexistuje. Triáž, karta, původní intake,
zdrojová data a závislosti se neměnily. Zbývá prompt a API adaptér extraktoru.

Review a příprava propojení 16. 10. 2026: společný balíček otázky z jednoho
načítání definic; příklady uchovávají ID, nikoli kopie možností. Nový
`QuestionnaireFlow` respektuje pořadí a `podminka`, rozlišuje celý dotazník
a cílené větve; návrhy neaktivují další otázky. Přidáno `/moznosti`, CLI limit
doptání a kontrola výlučné možnosti „žádné“. `build_pipeline_packet()` vrací
hodnoty a zdroje bez barev, odmítnutý návrh má null. Diagram, stav review a API
jsou v `docs/llm-flow.md`, skutečný offline výstup se syntetickým extraktorem
v `llm_intake/pipeline_example.json`.
`uv run --locked python -m pytest -q`: 116 testů prošlo, z toho 30 nových;
`uv run --locked ruff check .`, formát upravených Python souborů,
`git diff --check`, místní odkazy a CLI `--help` / `--list` prošly.
Živě ověřeny dvě syntetické extrakce: vícenásobná volba `[7, 10]` a výlučná
volba `[12]`, obě ve stavu `needs_confirmation`, bez skutečného potvrzení.
Linux / Python 3.12, Windows se nespouštěl. Nejde o benchmark ani klinické
ověření; MASTER extraktor, automatická selekce témat, rozpočet celého kontaktu,
časy jednotlivých tahů a adaptér triáže/karty zůstávají dalšími úkoly.
Zdrojové definice, triáž, klíče a závislosti se neměnily.

MASTER extraktor 16. 10. 2026: `llm_intake/master.py` s vlastním promptem,
striktním schématem a pěti dosavadními syntetickými příklady. `Client.send`
a `structured_payload` sdílejí API transport s původním intake. Extraktor
vrací fakta, kód navrhne kandidátní otázky pro šest témat a zachová nenamapované
pojmy a neurčené subjekty. Popření ani potíž pečujícího sama nevyvolají dotaz
na pacienta. Přidáno samostatné CLI pro zaznamenaný MessageEvent a ukázkové
vstupní/výstupní JSON; výstupní ukázka pochází z živého syntetického volání.
`uv run --locked python -m pytest -q`: 149 testů prošlo (33 nových),
Ruff, kontrola formátu změněných Python souborů, `git diff --check`, místní
odkazy, CLI `--help` a validace ukázkového výstupu prošly.
Tři živé syntetické scénáře ověřily: zvracení + únavu a popřenou teplotu;
přibližný počet průjmů pacienta a vlastní únavu pečujícího; nejistou teplotu,
popření zvracení a zachovanou nenamapovanou nespavost. Nejde o benchmark ani
klinické ověření. Linux / Python 3.12; Windows se nespouštěl.
Závislosti, zdrojové definice, klíč, triáž a karta se neměnily. Zbývá napojení
kandidátů a již známých hodnot na omezený dialog, potvrzování a širší pokrytí
pojmů; naléhavost a časování nadále patří do jiných částí systému.

Review modulu a rozhraní pipeline 16. 10. 2026: provedena kontrola chronologie a logiky
všech 4 dotazníků v dotazniky_definice.json (25 otázek nezadouci_ucinky, 9 psychoonkologicky_screening,
5 bolest_analgeticka_terapie, 10 esas). Zhodnoceno RAG vs. in-context katalog: RAG zatím odložen: pro 49 otázek používáme přímý katalog a Structured Outputs.
Srovnávací benchmark neproběhl; rizika negací a prahu podobnosti vyžadují měření.
Validace JSON schématu je samostatná a použití RAG ji samo o sobě nevylučuje.
Pro snadné napojení do celkové pipeline přidáno find_question() (dohledání i bez znalosti dotazníku),
QuestionnaireFlow.for_targets() (automatické odvození dotazníku z cíle) a create_targeted_session().
Veřejné API exportováno v kořeni llm_intake.
`uv run --locked python -m pytest -q`: 153 testů prošlo (4 nové);
`uv run --locked ruff check .` a `git diff --check` prošly. Linux / Python 3.12.

Sanity check a pull 16. 10. 2026: začleněny tři commity po `6818539`
až po `7b6e26f`; konflikty v decisions.md a tasks.md vyřešeny zachováním
obou stran. CLI zachovává `/moznosti`, limit doptání i novou triáž po potvrzení.
Opraveno předčasné načítání MASTER modulu při `python -m llm_intake.master`
bez změny veřejných exportů. Dokumentace rozlišuje pipeline fakta, omezené
propojení CLI a porovnání barev formulářů; závěr o RAG zúžen na dosavadní volbu
bez srovnávacího benchmarku. Prošlo 159 testů, Ruff, MASTER CLI s varováními
jako chybami, import veřejného API, načtení JSON a 36 místních odkazů.
Linux; bez živého LLM volání, Windows ani nového klinického ověření.
Zbývá napojení MASTER kandidátů na dialog, kartu a úplná triážní pravidla.

Interaktivní MASTER 16. 10. 2026: nový `llm_intake/dialogue.py` propojuje
extraktor s intake přes `seed(messages)` a `submit_event(message)`. Zachovává
skutečné otázky, autory, ID a dostupnost zpráv, potvrzování i opravy. Každá
slovní odpověď projde obecnou extrakcí, nová témata se přidají po uzavření
aktivní otázky. Výchozí rozpočet 6 počítá MASTER, doptání, potvrzení a opravy;
limit jednotlivého parametru zůstává 2. JSON lze vypsat nebo uložit do `.scratch/`,
včetně nevyřešeného a přerušeného stavu. Cílené CLI a triáž se neměnily.
`uv run --locked python -m pytest -q`: 183 testů prošlo (24 nových),
Ruff, kontrola formátu šesti Python souborů, `git diff --check`, CLI `--help`
a 39 místních odkazů prošly.
Živý syntetický MASTER průchod: zvracení za 24 hodin šlo rovnou k potvrzení,
únava po jednom doptání na odpočinek; obě odpovědi potvrzené, čtyři otázky
celkem, konečný JSON v `/tmp` ověřen včetně původu a stavu `complete`.
Živý cílený průchod „ne, nejde mi spat“ se doptal na odpočinek bez spánku,
po upřesnění správně vybral index 1 a nechal ho potvrdit. Prototyp triáže
nad únavou nadále vrací neurčeno. Nejde o benchmark nebo klinické ověření.
Kontroly na Linuxu / Pythonu 3.12; Windows se nespouštěl. Definice dotazníků,
klíč, závislosti a triážní moduly se neměnily. Zbývá širší mapování témat,
nezávislé měření kvality, řešení rozporů a klinická integrace.

Úplný katalog MASTER 16. 10. 2026: původní směrování šesti témat nahrazuje
`llm_intake/question_topics.json`, přesně 49/49 otázek ze všech čtyř dotazníků
ve zdrojovém `rakathon_meddi_onco_data/docs/dotazniky_definice.json`.
Každé téma má klíčová slova, aliasy a kontext; texty a možnosti zůstávají
v jediném zdroji. LLM dostává celý katalog a vrací `topic_ids` omezené enumem;
kód ID ověřuje a mechanicky páruje do stávajícího flow. Popření, pečující,
neznámé pojmy a původní citace se zachovávají. Po limitu jsou další otázky
v `dialogue.pending_topic_ids`. RAG ani další závislosti nepřibyly.

`uv run --locked python -m pytest -q`: 250 testů prošlo. Ruff check,
Ruff format --check (23 souborů v llm_intake a tests), `git diff --check`
a 44 místních odkazů prošly; CLI evaluátoru ověřené přes `--help`.
Ukázkový `llm_intake/master_output.example.json` byl obnoven skutečným
voláním nad syntetickým vstupem a obsahuje nová `topic_ids`.
Živá regrese nad 53 syntetickými případy mimo promptové příklady zachytila
55/55 minimálně očekávaných výskytů témat. Kontroly negací a pečujícího
nevygenerovaly zakázané pacientské kandidáty, nespavost a nepokryté kognitivní
sdělení zůstaly viditelné. Při prvním souběhu tří požadavků vrátila brána
u 21 případů HTTP 429; tyto případy znovu samostatně prošly se souběhem 1.
Výchozí souběh evaluátoru je proto 1. Chyby API se v reportu počítají zvlášť,
nejsou sémantickou chybou modelu ani úspěšným prázdným výsledkem.
Reporty jsou lokálně v ignorovaném `.scratch/`, sloučený přehled
`master-topics-verified.json` zachovává poznámku o opakování.

Model vrátil také 10 přiřazení nad minimální očekávání (např. explicitně
popřený příznak, doplňující popis krvácení a související účinky analgetik).
Záchyt 55/55 není měření přesnosti přiřazení ani záruka bezchybných budoucích
odpovědí. Sada je technická syntetická regrese, nikoli klinické ověření.
Linux / Python 3.12; Windows se nespouštěl. Zdrojové definice, triáž,
klíč a závislosti se neměnily. Zbývá vyhodnocení celého rozhovoru a klinická integrace.

Efektivita a přesnost LLM 16. 10. 2026: API reprezentace MASTER ponechává
texty, možnosti, návody a poznámky všech 49 otázek. Vynechává technická metadata
pořadí a podmínek zpracovávaná kódem, poznámku formuláře posílá jednou a používá
kompaktní JSON. Cílený extraktor vybírá nejvýše 3 relevantní příklady místo
všech 13. Výběr nefiltruje témata podle slov pacienta. Vyčerpaný limit kontaktu
se kontroluje před další cílenou extrakcí včetně přechodu po potvrzení.
Callback `Client.on_usage` předává pouze tokeny/cache/reasoning a dobu volání;
chybějící metriky jsou null. Není přidaná runtime závislost ani změněný model.

Na stejných syntetických požadavcích brána naměřila MASTER 16 169 → 11 605
vstupních tokenů (−28,2 %) a cílenou únavu 5 598 → 2 457 (−56,1 %).
Jde o jednotlivé požadavky, nikoli průměr kontaktů nebo příslib ceny/latence.
Lokální porovnání: `.scratch/llm-usage-comparison.json`.

Při první optimalizaci přesun katalogu do systémové části způsobil u citlivého
syntetického screeningu HTTP 400 `content_filter` / `ResponsibleAIPolicyViolation`.
Kontrolní původní payload prošel. Konečná varianta ponechává katalog a zprávu
ve stejném uživatelském vstupu, statickou část před polem message; případ znovu
prošel. Žádné bezpečnostní nastavení brány se neměnilo. Klient odlišuje blokaci
od chyby schématu a při selhání první analýzy dialog uchová zprávu se stavem
`processing_error`. Test pokrývá i její uložení přes CLI `--output`.

Konečný živý běh obou sad: 68/68 případů, 74/74 očekávaných výskytů témat,
bez chyb API/validace. Na 15 případech s úplnou anotací povolených témat
19/19 vrácených témat povolených; prošly i kontroly subjektu, negace, změny
v čase a hodnoty včetně nuly, vícetématový vstup a vložené pokyny pro model.
Zbývajících 53 případů má pouze minimální očekávání: 8 přiřazení navíc zahrnuje
popření a související otázky; nepovažujeme je automaticky za falešná přiřazení
ani z této sady neodvozujeme přesnost. Report `.scratch/master-optimized-final.json`
obsahuje všechny výsledky i usage: 788 612 vstupních a 6 861 výstupních tokenů;
brána hlásila 161 074 cached tokenů, proto nepředpokládáme cache celého katalogu.

Dalších 9 živých cílených scénářů prošlo: přímé přiřazení, oprava únavy,
počet zvracení, více účinků, rozpor „žádné“, škála zvládání, SOS počet a vlastní
únava pečujícího. Lokální `.scratch/targeted-optimized-evaluation.json` obsahuje
vstupy i očekávání; tento průchod byl jednorázový, nejde o celý klinický dialog.
`uv run --locked python -m pytest -q`: 260 testů prošlo. Ruff check,
Ruff format --check (24 souborů), 47 místních odkazů, CLI `--help`
a `git diff --check` prošly. Linux / Python 3.12, Windows se nespouštěl.
Zbývá větší nezávislá anotovaná sada a ověření celého kontaktu; syntetické
výsledky negarantují obecnou ani klinickou přesnost. Definice, klíč,
závislosti a triážní moduly se neměnily.

Sanity check před publikací 16. 10. 2026: `git pull --ff-only origin main`
byl aktuální na `1435d2b`, konflikty nevznikly. Zkontrolovány změny dialogu,
zdrojových událostí, katalogu témat a evaluátoru. Prošlo 260 testů
(`uv run --locked python -m pytest -q`), Ruff, CLI `--help` pro master,
dialogue a evaluate_topics s varováními jako chybami, načtení změněných JSON,
47 místních odkazů a kontrola konfliktových značek. Lokální `.env` je ignorovaný.
Ověření proběhlo na Linuxu bez živých API volání; Windows a klinická
správnost se nově neověřovaly. Zbývá nezávislé vyhodnocení celého dialogu
a napojení na kartu a úplná triážní pravidla.

Napojení pipeline paketu na triáž a kořenové exporty 16. 10. 2026: doplněn
adaptér `evaluate_pipeline_packet` a rozšířena funkce `evaluate_intake` v `triage.py`
pro přímé mapování celého paketu (potvrzené odpovědi i naměřená fakta pacienta,
např. teplota) včetně volitelného kontextu léčby (chemoterapie z karty).
Kořenový balíček `llm_intake` exportuje `MasterDialogue`, `load_topic_catalog`
a `resolve_topics`. Prošlo 262 testů (`uv run --locked python -m pytest -q`,
2 nové testy), Ruff check a `git diff --check`. Linux / Python 3.12.

Porovnání s `d1b58f4` a pull 16. 10. 2026: kód sloučen bez textového
konfliktu; rozhodnutí a úkoly obnovují smazanou historii LLM. Podrobné
zdůvodnění a otevřené problémy jsou v [merge-review.md](merge-review.md).
Před opravou mapování prošlo 494 testů; po osmi regresních případech 502.
Ruff prošel. Zdroje organizátorů, závislosti a nové klinické pravidlové jádro
se při řešení konfliktů neměnily. Živý LLM ani Windows se nespouštěly.
Zbývá časově a zdrojově doložený adaptér do meddi/ a domluva politiky
nejistoty; původní pipeline adaptér zůstává omezeným prototypem.
