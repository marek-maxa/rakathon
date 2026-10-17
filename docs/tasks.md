# Úkoly MEDDI ONCO

Stavy: `todo`, `doing`, `blocked`, `done`. Jeden vlastník na úkol.
Implementační kroky zahajujeme po společné domluvě, postupně.

Aktuální navazující pořadí K1–K10 a přijímací podmínky určuje
[plán pipeline a webu](meddi-onco-plan.md), §9. Původní relace zvolila pouze plán;
následně tým povolil merge main do web a napojení zobrazení barev a problémů.
Starší `todo` níže zůstávají jako historie a tematický
backlog; při další práci je konkretizovat příslušným K krokem, nespouštět
všechny souběžně. Dřívější odklad webu není cílovým omezením nového plánu.

| Úkol / rozsah souborů | Vlastník | Stav | Hotovo, když |
| --- | --- | --- | --- |
| Jeden zvolený webový dotazník a nepovinná zpráva na konci; llm_intake/dialogue.py, web/app.py, export.py, templates/index.html, testy a docs/ | Aktuální relace / web | done | Výběr všech čtyř definovaných formulářů, výchozí Nežádoucí účinky; kompletní větvení bez limitu 6, zpráva nebo přeskočení před souhrnem, stejná extrakce a pravidla; 751 testů a Ruff prošly. Nasazení čeká na aktualizaci Azure |
| Zapnout zprávy ve výchozím main.py a odhalit neprovedené LLM vyhodnocení; main.py, meddi/messages.py, testy a docs/ | Aktuální relace / web | done | Běžný CLI běh zahrnuje zprávy, offline režim výslovný, stav v tabulce i bez details, při chybě návratový kód 1 a vysvětlení. 740 testů a živý ONC-018: 8 complete / 0 failed / 5 bez zprávy |
| Zprávy pacienta přes existující LLM → fakta → společná pravidla; meddi/messages.py, pipeline/validation, llm_intake/master*, main.py, web report/store/templates, testy, pyproject/uv.lock a docs/ | Aktuální relace / web | done | Explicitní rozpory a doptání se zdroji, zachovaná horší varianta, žádné barvy od LLM, opakovaný report bez API, čas a reference oddělené; 736 testů a balíček ověřeny. Živý LLM neověřen: místní klíč chybí; bez nasazení |
| Odstranit určování triáže barvou možnosti a zachovat konkrétní konzervativní výsledek; meddi/triage.py, clinical_rules.py, testy a docs/ | Aktuální relace / web | done | Žádné převzetí zobrazovací barvy; konkrétní výsledek 1–4, nejistota navázaná na pravidlo, rules_version=5, 708 testů a 171 strukturovaných check-inů ověřeno; bez nasazení |
| Vyřešit konflikty při merge origin/main do web; web/app.py, docs/architecture.md, docs/tasks.md, balicí skript a testovací podpora | Aktuální relace / web | done | Zachované Basic Auth i MASTER relace a nové podklady; 681 testů, Ruff a kontrola rozbaleného Azure ZIPu prošly. Merge připravený k ručnímu commitu; bez nasazení |
| Připravit a nasadit současný Flask demo web na Azure; scripts/package_azure.py, pyproject.toml, uv.lock, docs/ | Aktuální relace / main | done | ZIP bez tajemství a referencí, lokální testy, nastavený Gunicorn, úspěšný Azure build a ověřené vzdálené přihlášení, formulář, statika i report |
| Doplnit MEDDI_LLM_API_KEY v Azure a ověřit syntetickou odpověď | Tým | todo | Klíč nastavený přes Azure Portal bez sdílení v chatu; potvrzený průchod LLM formulářem. Klíč při nasazení nebyl lokálně ani v Azure dostupný |
| Ochrana webu HTTP Basic Auth; web/app.py, tests/test_web_auth.py, llm_intake/.env.example, docs/ | Aktuální relace / main | done | Všechny cesty chráněné, chybějící konfigurace odmítne přístup, ověřené chybné i správné údaje; zdokumentované Azure proměnné a HTTPS. Vzdálené nastavení a nasazení ještě neprovedeno |

| Audit nadměrné eskalace po odstranění neurčeno; coverage, triáž, testy a docs/triage-coverage-audit.md | Aktuální relace / web | doing | Vysvětlené příčiny všech 109 review-only žlutých výsledků. Běžné/mírné odpovědi a vyřešené větvení se skutečně vyhodnotí; neodkládat chybějící odpovědi, texty nebo neznámé měření jen kvůli počtu zelených. Ověřit celou časovou sadu i syntetické proti-příklady bez použití referencí při rozhodování |
| Nahradit konečné neurčeno konkrétním krokem; meddi/disposition.py, triage/pipeline, webový adaptér a šablony, testy a docs/ | Aktuální relace / web | doing | Každý posuzovaný kontakt má úroveň 1–4 a doporučený kontakt/krok. Nevyhodnocené aktuální údaje vedou alespoň ke žluté; neúplnost zůstává oddělená, známá 3/4 se nesnižuje, neaktivní hypotetická pravidla neeskalují rutinní záznamy. Ověřit uložené výsledky, Patient 1 a celé testy |
| Zachovat rizikovou úroveň při neúplné triáži; meddi/triage.py, meddi/clinical_rules.py, web/triage.py, regresní testy a docs/ | Aktuální relace / web | done | Nepokryté nezelené odpovědi a doložené příznaky s neznámým léčebným kontextem mají zdrojované předběžné minimum; známé klinické pravidlo má přednost. Staré reporty se přepočítají ze zmrazených vstupů. 608 testů, Ruff, formát změněného Pythonu a git diff --check prošly; 14 reportů / 174 místních check-inů bez neurčené triáže s oranžovou/červenou odpovědí. Klinické mapování neobarvených odpovědí a kontrola falešných poplachů zůstávají otevřené |
| Opravit předčasné zobrazení výsledku triáže; web/templates/index.html, tests/test_survey_recovery.py, docs/ | Aktuální relace / web | done | Triáž všech barev se zobrazí až po potvrzení a úspěšném uložení; během doptávání a kontroly souhrnu žádný blok triáže ani průběžné upozornění. Prošlo 39 webových testů bez sítě, Ruff, formát a git diff --check |
| Sloučit aktuální main do web a zobrazit barvu i problémy společné triáže; web/triage.py, web/app.py, report, šablony/CSS, testy a docs/ | Aktuální relace / web | done | Zachované rozpracované změny, merge 272581c, backendové důvody a neúplnost ve formuláři i reportu; uložené vyhodnocení s celým kontaktem; 583 testů, Ruff, formát a všech 14 reportů prošlo bez sítě |
| Ukládat dotazníky do pracovní kopie pacienta; web/app.py, web/patient_store.py, web/patient_report.py, tests/test_survey_recovery.py, README.md, docs/ | Aktuální relace / web | done | Nové check-iny přibývají do data/pacienti/<patient_id>.json, zůstává historie a kontext, originály se nemění, report načítá pracovní kopii a zápis je atomický |
| Obnovit webový MASTER průchod po chybném rebase; web/, llm_intake/, tests/, README.md, docs/, .gitignore | Aktuální relace / web | done | Zachované profily a reporty, cílené doptání a společná kontrola odpovědí; atomické uložení pod vybraným pacientem, ochrana dokončeného formuláře a ověření bez sítě |
| Úplná revize zadání a plán pipeline → web; docs/meddi-onco-plan.md, challenge.md, architecture.md, decisions.md, tasks.md, README.md, historické přehledy | Aktuální relace / main | done | Všechny dostupné podklady MEDDI znovu přečtené; 27 zdrojovaných požadavků, zpracované komentáře týmu, 12 otevřených závislostí a kroky K0–K10 s podmínkami dokončení. Prošlo 543 testů, Ruff, strukturovaný replay, 65 místních odkazů a kontrola úplnosti seznamů. Pouze dokumentace podle upřesnění týmu; aplikace ani větve se neměnily |
| K1 · kompatibilní webový základ; existující web/, manifest a lock ve větvi web | Aktuální relace / web | done | Main převzat, zachovaný formulář, styly a JS, skutečné API MASTER/doptání/společného potvrzení/opravy ověřené falešným LLM; stav sběru je oddělený od backendové triáže. K2–K10 tím nejsou splněné |
| K2 · stabilní identita a úplné uložení; úložný adaptér, karta, web/app.py a export | Tým | todo | Originál před LLM, celý paket a revize po načtení, neúplnost a autor zachované, ochrana před duplicitami; závisí na domluveném kontraktu |
| K3 · časový kontext a poslední chemoterapie; patient_inputs, karta a adaptér | Tým | todo | Skutečné podání oddělené od plánu a typu cyklu, odstup se zdrojem, časová hranice bez budoucích informací; po K2 |
| K4 · průběžná a závěrečná orchestrace; aplikační služba, dialogue, web | Tým | todo | Vyhodnocení před dalším cíleným LLM voláním, okamžitá red instrukce, závěrečná/přerušená revize uložená bez ztráty faktů; po K2/K3 |
| K5 · klíčové/varovné nálezy a cílené sledování; karta, kontroly, existující flow | Tým | todo | Nezelené nálezy sledované, zlepšení zachované, varovné podmnožinou, bez duplicitních otázek a vymyšlených intervalů; po K2–K4 |
| K6 · doporučení, kontakty, předání a souhrn; výstupní politika a adaptéry | Tým | todo | Zdůvodněný krok pro všechny úrovně, pracovní doba a zvláštní lhůty, evidované předání a souhrn se zdroji; po K3–K5 |
| K7 · text, nejistota a klinické mezery; registry adaptéru, mapování a doptání | Tým + mentor | todo | Vyřešené relevantní alternativy a zdrojové rozpory podle plánu §10, bez ladění pravidel podle ID/reference; návazně na K3–K6 |
| K8 · karta a pohled týmu v existujícím webu; Flask/Jinja/CSS | Tým | todo | Aktuální nálezy, časová osa a kontroly s dohledatelnými zdroji, srozumitelný krok a oddělená oprávnění; po K1–K7 |
| K9 · úplný replay a soutěžní demo; evaluátor, fixtures a testy | Tým | todo | Všech 171 check-inů a šest situací bez budoucích dat, oddělené reference, záchyt i falešné eskalace a záložní demo; po K4–K8 |
| K10 · MEDDI/AWS a provozní připravenost; adaptéry, konfigurace a dokumentace | Tým + pracoviště | todo | Rozhraní, EU cesta dat/LLM, přístupy, obnova a doručení i klinické/provozní převzetí vyřešené; skutečné nasazení je další krok |
| Vymezit klíčové nálezy, varovné příznaky a doporučení; AGENTS.md | Aktuální relace / main | done | Pracovní výklad týmu je v kořenových instrukcích: varovné příznaky tvoří podmnožinu klíčových nálezů, vedou k 3/4, klíčové nálezy obsahují i zlepšení a jsou podkladem doporučení |
| Research neshod triáže a konkrétní plán změn; docs/tasks.md, lokální .scratch/ | Aktuální relace / main | done | Nový běh všech 171 check-inů, vysvětlení všech lower/higher, kontrolní dosazení chybějících vstupů, primární zdroje pro spornou gradaci a kroky oddělené od neschválených klinických výkladů; bez změny aplikačního kódu. Rozbor je na konci tohoto souboru v oddílu Research neshod triáže |
| Sjednotit výpočetní backend a opravit doložené chyby; meddi/pipeline.py, meddi/validation.py, meddi/triage.py, meddi/clinical_rules.py, meddi/form.py, triage.py, ukázky, testy a docs/ | Aktuální relace / main | done | Jediné jádro pravidel, evaluate_contact a kompatibilní kořenová API; degC, konflikty podle času, NaN/nekonečno a dlouhodobá bolest opravené. 543 testů (41 nových), Ruff, formát, syntetické CLI a JSON prošly; kontrakt v backend.md. Replay zůstává 132/171, 30 nižších a 9 vyšších. Web, karta a plné klinické ověření mimo rozsah |
| Revize připravenosti pipeline LLM → triáž → karta; docs/pipeline-readiness.md, architecture.md, decisions.md, tasks.md | Aktuální relace / main | done | Main 0420073, fetch web 6aeb385, 502 testů a Ruff prošly; reference 132/171 shod, 30 nižších, 9 vyšších. Reprodukovány nesoulad degC, závislost na pořadí, NaN, chybná negace dlouhodobé bolesti, ztrátový web export a nekompatibilní API. Konkrétní integrační krok v pipeline-readiness.md; bez změny aplikačního kódu |
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
| Vícekrokový formulář propojený s backendem; web/, llm_intake/core.py, tests/test_web.py, docs/, README.md, pyproject.toml, uv.lock | Aktuální relace / main | done | Nechat chatové bubliny mimo rozhraní; serverové formuláře, potvrzení/upravení výběru, doptání, pokračování bez přiřazení a chyby zřetelně oddělené od formuláře |
| Návrh MASTER QUESTION a propojení; docs/master-question.md, docs/architecture.md, docs/decisions.md, docs/tasks.md | Aktuální relace / main | done | Prověřené aktuální moduly a podklady; zdrojované mezery, tok zprávy/faktů/otázek/karty, konzervativní triáž bez falšování faktů, limity zátěže a malé implementační kroky; zatím jen návrh bez změny běžícího API |
| Minimální LLM kontrakt faktů a první katalog; llm_intake/master_contract.py, llm_intake/question_catalog.py, llm_intake/master_examples.json, llm_intake/MASTER_CONTRACT.md, tests/test_master_contract.py, docs/ | Aktuální relace / main | done | Samostatný formát zprávy a faktů se zdrojem, časovým textem a nejistotou; 49 dvojic ID a první vazby šesti témat, pět syntetických příkladů; 86 testů a Ruff prošly, bez zásahů do triáže, karty a intake v2 |
| Extraktor MASTER QUESTION nad připraveným kontraktem; llm_intake/master.py, master_prompt.md, master_schema.json, client.py, ukázkové JSON, tests/test_master_extraction.py a docs/ | Aktuální relace / main | done | Striktní extrakce s pěti příklady a sdíleným transportem, kandidáti a nepokryté pojmy, CLI nad zaznamenanou zprávou; 149 testů a tři živé syntetické scénáře prošly. Bez triáže, karty a automatického rozhovoru |
| Napojit kandidáty MASTER na omezený dialog a potvrzování; llm_intake/dialogue.py, core.py, client.py, flow.py, pipeline.py, prompt.md, tests/test_master_dialogue.py a docs/ | Aktuální relace / main | done | Interaktivní MASTER i vstup ze souboru, původní otázky a zdroje, potvrzení/oprava, nová témata a podmíněné větve, rozpočet včetně potvrzení a JSON; 183 testů, Ruff a dva živé syntetické CLI průchody prošly; cílené CLI a triáž zachované |
| Vyhodnotit celý MASTER dialog; llm_intake/ a oddělené evaluační příklady | Nepřiřazeno | todo | Katalog všech otázek a samostatná regrese rozpoznání témat už existují; zbývají nezávislé scénáře správnosti potvrzené možnosti, počtu dotazů, rozporů a nevyřešených kontaktů. Samostatně klinická integrace a pravidla |
| Zpřesnit klinické alternativy a smlouvu s kartou; docs/master-question.md, docs/backend.md, docs/architecture.md | Tým | todo | Základní kontrakt nad meddi/ již implementován. Zbývají podložené intervaly/alternativy, obecný relativní čas, výběr aktuální epizody producentem karty a rozpory definic průjmu a NRS |
| Opravit doložené chyby před integrací; triage.py, meddi/clinical_rules.py, hranice vstupů a regresní testy | Aktuální relace / main | done | Zahrnuto do společného backendu 17. 10.; degC, pořadí/čas/konflikty, nekonečná/NaN měření a dlouhodobá bolest pokryté regresními testy |
| Navázat společný backend na kartu, orchestraci a web API | Tým | todo | LLM → meddi a syntetické uložení/načtení celého JSON již ověřeno. Aktuální konkretizace je K1–K8: bezpečnostní bod před dalším cíleným LLM, závěrečná revize, úplné úložiště, stabilní patient_id a skutečné potvrzovací API. Přenos do webu je nový cíl; tato relace pouze plán |
| S mentorem potvrdit nejasnosti pravidel a časových údajů; docs/challenge.md, docs/architecture.md | Tým + mentor | todo | Známá dostupnost údajů v čase, vyřešené interpretační otázky, případné dodatečné hodnoticí rozhraní, termín a způsob odevzdání |
| Společně projít jeden případ a domluvit schéma extrakce a karty; docs/architecture.md | Tým | todo | Definovaná pozorování se zdrojem a časem, jejich použití v pravidlech a výstupy pro pacienta i zdravotníka; zvolený nejmenší implementační krok |
| První průchod načtení → triáž → výstup | Nepřiřazeno | todo | Po domluvě předchozího kroku konkretizovat soubory; jeden případ běží s dohledatelnými důvody a bez budoucích dat či referencí ve vstupu |
| Vyhodnocení všech šesti povinných situací a hraničních vstupů | Nepřiřazeno | todo | Časové přehrávání, podhodnocení závažnosti a zbytečné poplachy mají ověřitelné výsledky; klinickou interpretaci prošel mentor |
| Demo pro pacienta a tým, návrh integrace | Nepřiřazeno | todo | Srozumitelný další krok, souhrn a simulované upozornění; opakovatelný scénář i záloha bez externí služby |

Bezpečnostní oprava neúplné triáže 17. 10. 2026: podle pravidel §3 a §6.4
zavedené předběžné minimum pro nepokryté nezelené odpovědi a doložené
příznaky s neznámým léčebným/rizikovým kontextem. Reprodukované neurčeno
s červeným ESAS nyní zachovává předběžnou červenou, bez převodu ESAS na NRS.
Změněné soubory: `meddi/triage.py`, `meddi/clinical_rules.py`, `web/triage.py`,
šest regresních testových souborů a dokumentace. Bez změny zdrojových pacientů,
referencí, závislostí či neobarvených klinických mapování.

Ověření: `uv --cache-dir /tmp/rakathon-uv-cache run --locked --no-sync python -m pytest -q`
— **608 prošlo**; Ruff check celého projektu, formát devíti dotčených Python
souborů a `git diff --check` prošly. Globální formát našel již dříve
neformátované Python ukázky v Markdownu `architecture.md`, `backend.md`
a `llm-flow.md`; ty nebyly přeformátovány. Výchozí uv cache byla pouze pro
čtení, proto kontroly používají zapisovatelnou cache v `/tmp`.
Flask test klient načetl všech **14 reportů / 174 místních check-inů**;
žádná oranžová/červená odpověď neměla výslednou barvu neurčeno.
Replay původních **171** check-inů: **121 shod, 23 nižších, 27 vyšších**, 25
předběžných výsledků; dříve 132/30/9. Červené reference zachyceny 5/6,
`ONC-011-C09` zůstává oranžový. Větší počet vyšších výsledků je důsledek
konzervativní politiky; nutné klinické review, zejména ESAS gradientu.
Reference byly pouze vyhodnocení, nikdy rozhodovací vstup.

Upřesnění ONC-001: C07 (9. 9., 38,4 °C po chemoterapii) již vrací červenou.
Poslední místní webový kontakt (17. 10., kožní potíže a částečná soběstačnost)
má neobarvenou kožní odpověď a zelenou možnost soběstačnosti, bez dostatečného
klinického mapování. Není podklad pro automatickou červenou z dávné horečky;
závažnost aktuálních neobarvených obtíží zůstává otevřenou mezerou K7/O3.
Zdroj: pacient ONC-001, C07 a aktuální pracovní kopie; pravidla §3, §6.3;
definice `nezadouci_ucinky/kuze` a `sobestacnost`.

Revize zadání a plán 17. 10. 2026: znovu přečteno celé pořadatelské PDF
(13 stran, s. 5–12 také vizuálně), všech 6 slidů PPTX včetně poznámek, README
balíčku, pravidla §1–6, pacientská cesta, čtyři vzorové souhrny a všech
49 otázek. Přečtena týmová dokumentace a LLM kontrakty/prompty; čtením kódu
ověřeny hranice backendu a dostupný web `origin/web=6aeb385`, bez fetch,
přepnutí větve či spuštění Flasku. Aktuální main `ca8ebd1`.
[Výstup](meddi-onco-plan.md): požadavky P01–P27, komentáře týmu,
úplný inventář klinických skupin, návrh datového toku a záznamů, otevřené
závislosti O1–O12 a kroky K0–K10 se soubory, návaznostmi a podmínkami dokončení.
Zásadní nález: bezpečnostní vyhodnocení musí předcházet dalšímu cílenému LLM
volání uvnitř dnešního dialogu. Web má nekompatibilní potvrzovací API
a ztrátový export; první krok využije existující UI a skutečné API.

Skutečně provedené kontroly této revize: `uv run --locked python -m pytest -q`
— **543 prošlo**; `uv run --locked ruff check --no-cache .` prošel;
`uv run --locked python main.py` — **132/171 shod, 30 lower, 9 higher,
171 review**, nadále dvě podhodnocené referenční červené. Místní audit potvrdil
14 pacientů, 171 check-inů, 96 neprázdných zpráv, 3 nevyplněné check-iny,
4 dotazníky/49 otázek a reference 115/37/13/6; žádná reference úrovně 1/2
nemá neprázdné varovné příznaky. Reference byly použity jen pro oddělený
audit/porovnání. První pomocný auditní skript chybně předpokládal objekt
reference místo seznamu; po opravě kontrola prošla, zdrojové soubory beze změny.
Prošlo 65 místních odkazů v osmi měněných Markdown souborech, kontrola úplnosti
27 požadavků / 11 kroků / 12 závislostí, uzavření bloků kódu a `git diff --check`.
Kontroly na Linuxu / Pythonu 3.12, bez živého LLM, Windows, webového serveru,
nasazení či nového klinického ověření. Měnila se pouze dokumentace;
žádný commit/push, změna aplikace, zdrojů nebo závislostí. Zbývá po domluvě
začít K1 a potvrdit příslušné otevřené výklady s mentorem.

Sjednocení backendu 17. 10. 2026: `uv run --locked python -m pytest -q` —
543 testů prošlo (41 nových případů v `tests/test_backend_pipeline.py`).
`uv run --locked ruff check --no-cache .`, kontrola formátu všech sedmi
měněných Python souborů a `git diff --check` prošly. Spuštěno skutečné offline
CLI `python -m meddi.pipeline` nad syntetickým kontaktem/snapshotem, ověřen
JSON roundtrip, zachování celého intake a nahrazení staré normální teploty
novým údajem. MasterDialogue s falešným extraktorem ověřil červené minimum
před potvrzením i po něm. Nové regrese pokrývají pořadí/rozpory, nízkou i vysokou
glykemii, budoucí a expirované vstupy, identitu pacienta, doslovnost citací,
nejasný čas/interval, jednotky a neplatná čísla; shodná možnost a přesné měření
nevytvářejí falešný rozpor, skutečný rozpor teploty zachová červené minimum. CLI `--help` prošlo.
Opakované porovnání dodaných fiktivních dat: 132/171 shod, 30 nižších a
9 vyšších úrovní, 171 případů k review; z šesti červených referencí čtyři
červené a dvě oranžové. Tato čísla se proti revizi nezměnila a nejsou
klinickým potvrzením správnosti; doplnění textových pozorování a plné §6.4
zůstává otevřené. Nový kontrakt a příkaz v [backend.md](backend.md).
Kontroly na Linuxu / Pythonu 3.12, Windows se nespouštěl. Bez volání LLM,
změny závislostí, zdrojových dat, webu nebo uložení skutečné karty.

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

Oprava rebase 17. 10. 2026: kolegův web z `6aeb385` obnoven se zachováním
výběru profilu a reportů. Potřebné MASTER moduly a jejich regresní testy převzaty
z lokálního `main`; doplněna společná kontrola, slovní opravy a zneplatnění
podřízených odpovědí při opravě rodiče. Potvrzení uloží samostatný JSON pod
`data/<patient_id>/`; ID vychází z úvodního výběru. Chyba atomického zápisu
zachová nepotvrzený souhrn, dokončený průchod odmítá další POSTy kromě výslovného
restartu. Data jsou ignorovaná Gitem. Původní reporty, meddi/, CSS, form.js,
pyproject.toml a uv.lock zůstaly beze změny; tři původní nesledované testovací
soubory zachovány, v test_web.py upravena dvě očekávání pro obnovený tok.

Ověření: `uv --cache-dir /tmp/rakathon-uv-cache run --locked --offline pytest -q`
— 213 testů prošlo. Ruff check, format --check pro změněný Python a intake
dokumentaci, `git diff --check` a CLI `python -m llm_intake.dialogue --help`
prošly. Testy používají syntetické vstupy bez sítě a dočasné adresáře: vybraný
profil ve výstupu, dva různé profily současně, opravy, podmíněné větve, limit,
nevyřešené hodnoty, opakovaný POST, chyba API i zápisu a opakování uložení.
Kontroly proběhly na Linuxu s Pythonem 3.12; cache byla přesunuta do /tmp kvůli
omezení zápisu v prostředí. Windows, živý model ani klinická interpretace nebyly
nově ověřeny. Rozpracované relace se po restartu neobnovují a historické reporty
zatím nové uložené dotazníky nenačítají. Žádný commit ani push vytvořen.

Upřesnění ukládání 17. 10. 2026: existující `data/pacienti/` je pracovní kopie
zdrojového balíčku, kterou samostatné exporty obcházely. Dohledaný commit
`6aeb385` už používal samostatné exporty; dřívější automatické přidávání do
kopie se z prohlédnuté historie nepotvrdilo. Na pokyn týmu nyní web přidává
check-in do `data/pacienti/<patient_id>.json`, při chybějící kopii použije
originál jako základ. Zachovává kontext a historii, zámek v procesu chrání
souběžné zápisy a opakované checkin_id se neduplikuje. Report čte pracovní
kopii, případně původní zdroj. CLI loader a reference se nemění.

Jeden existující samostatný export pro ONC-001 byl lokálně přidán do pracovní
kopie; export zůstal zachován a původní pracovní soubor má zálohu v
`/tmp/rakathon-patient-backup-camwtrv4/`. Hash kontrola všech 43 JSON pod
zdrojovým balíčkem a pracovními pacienty potvrdila jedinou změnu:
`data/pacienti/ONC-001.json`; žádný originál se nezměnil. Report tohoto pacienta
vrátil HTTP 200 a obsahoval přidaný WEB check-in.

Ověření: `uv --cache-dir /tmp/rakathon-uv-cache run --locked --offline pytest -q`
— 217 testů prošlo. Ruff check, format --check čtyř dotčených Python souborů
a git diff --check prošly. Testy navíc pokrývají nezměněný originál, zachování
historie a kontextu, opakované i souběžné přidání, zachování již uložené kopie
při chybě zápisu a report s novou odpovědí. Linux / Python 3.12, bez sítě;
Windows ani živý model se neověřovaly. Žádný commit ani push vytvořen.
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

## Research neshod triáže: podklady a kroky

Tento oddíl je aktuální rozbor cesty `main.py` → `meddi/`, nikoli návrh
změnit barvy podle ground truth. Aplikační kód nebyl v tomto kroku měněn.
Dřívější pokyny týmu stále platí: zprávy nyní automaticky nezpracovávat,
nepřidávat vlastní klinické prahy, neznámé podmínky přeskakovat a uchovat.
Texty jsou zde přečtené pro vysvětlení neshod, ne jako nově zapojené vstupy.

### Ověřený výchozí stav a metoda

Nově spuštěno `uv run python main.py`: **132/171 shod, 30 lower, 9 higher,
0 undetermined, 171 review**. Každý záznam má některá nevyhodnocená kritéria;
green je minimum ze známých pravidel při současné vývojové politice, ne
potvrzení, že všechny příznaky jsou mírné nebo nepřítomné.

Byly přečteny aktuální odpovědi, měření, dostupný kontext a oddělené reference
všech 39 neshod. Referenční soubor slouží pouze k porovnání výsledku.
Zdroj konkrétního případu je vždy `rakathon_meddi_onco_data/pacienti/ONC-xxx.json`,
`checkiny[].checkin_id`; reference je stejné ID v odděleném `ground_truth/`.
Pravidla používají jen informace dostupné k času check-inu.

Provedeno také **24 kontrolních dosazení** strukturovaných pozorování do
existujícího jádra. Nejde o pacientem potvrzené údaje ani novou dosaženou
přesnost: jde o ověření, zda po dodání dané podmínky už existující pravidlo
vrátí očekávanou barvu. Výstupy jsou v ignorované lokální složce:

- `.scratch/triage-research-audit.json`: původních 39 neshod se vstupy a důvody.
- `.scratch/triage-research-counterfactuals.json`: 24 kontrolních dosazení,
  explicitně označených jako výzkumné a nepotvrzené skutečnosti.

### O co se opírá interpretace

Rozhodnutí o barvě čerpáme z
[pravidla_triaze.md](../rakathon_meddi_onco_data/docs/pravidla_triaze.md):

- **§3:** konkrétní podmínky minimální oranžové a červené.
- **§4, první odrážka:** obecný příznak 2. stupně bez varovných příznaků.
  Výčet nevolnosti, zácpy, aftů, paronychie a ruka-noha není nadepsán jako
  úplný seznam všech možných příznaků. Konkrétní mapování stupňů ale vyžaduje
  doložit, co daná odpověď skutečně znamená.
- **§4, odrážka Smutek nebo úzkost:** střední psychická zátěž, zátěž pečujícího,
  neadherence. Neobsahuje číselnou hranici škály 1–10.
- **§5:** léčba, chronický obvyklý stav a cyklická pauza mění posouzení.
- **§6.1:** trend; **§6.2:** přednost zprávy a řešení rozporu; **§6.3:** aktuální
  zlepšení po zásahu týmu; **§6.4:** doptání a vyšší možná úroveň.
  Poslední bod je v aktuální aplikaci dočasně nahrazen výslovným pokynem
  přeskakovat chybějící podmínky. Research tuto politiku potichu nemění.

Úvod pravidel odkazuje na CTCAE **v5**. Primární doplňkový zdroj pro význam
stupně je [NCI CTCAE v5](https://dctd.cancer.gov/research/ctep-trials/for-sites/adverse-events/ctcae-v5-8x11.pdf):
úzkost, s. 109; artralgie, s. 89; periferní senzitivní neuropatie, s. 104;
hypertenze, s. 145. U prvních tří je 2. stupeň spojen se středními obtížemi
a omezením instrumentálních denních činností. To je kandidátní opora pro
mapování konkrétních slovních odpovědí, není to převod libovolného skóre 1–10.
NCI také [výslovně rozlišuje pacientská skóre a klinické stupně](https://healthcaredelivery.cancer.gov/pro-ctcae/faqs.html)
v oddílech o skórování a vztahu PRO-CTCAE k CTCAE. MOÚ screening navíc není
v balíčku doložen jako totožný nástroj PRO-CTCAE.

Ve [veřejném popisu MEDDI Onkologie](https://www.meddi.com/cz/onkologie)
je screening uveden, ale nalezená stránka nedává jeho skórovací klíč.
Hledání na veřejných stránkách MOÚ a MEDDI neověřilo převod použité škály
1–10 na střední stupeň. To není důkaz neexistence klíče; potřebujeme jej
od zadavatele. Z jiného dotazníku, například HADS nebo teploměru distresu,
nepřebíráme hranici pro tento formulář.

### Konkrétně ONC-004-C08

Vstup obsahuje úzkost **6/10**, depresivitu **2/10**, zvládání **5/10**,
zájem o psychologa a obavu z další léčby. Referenční nález označuje úzkost
jako 2. stupeň. Při takto potvrzené střední úzkosti je podle §4 očekávaná
**yellow**. Referenční klinický stupeň ale není součástí vstupního dotazníku.

V kódu už je `moderate_psychological_distress` v `meddi/clinical_rules.py`.
Kontrolní dodání `moderate_anxiety=true` změnilo tento check-in z green na
yellow. Problém tedy není chybějící žluté pravidlo, ale chybějící doložené
mapování z odpovědi na jeho vstup. Nezakódovat `uzkost >= 6` na základě
jednoho referenčního případu. Konkrétní další krok je získat skórovací klíč,
nebo zachytit dopad úzkosti na činnosti a kvalifikovaně potvrdit stupeň.
Původní hodnota 6/10 i její zdroj mají zůstat zachované vedle odvozeného údaje.

### Kroky pro implementaci v doporučeném pořadí

| Priorita | Co přesně změnit | Kde | Opora a podmínka dokončení |
| --- | --- | --- | --- |
| 1 | Dodat do jádra již strukturovaná, zdrojovaná pozorování. Přijmout skutečné hodnoty včetně false a unknown, autora a čas dostupnosti. Neodvozovat je z reference | `meddi/patient_inputs.py`, volající `main.py`; využít existující argument `observations` v `meddi/triage.py` | §3–4 a §6.6. Například `slow_breathing` musí aktivovat stávající red, `orthopnea` stávající orange. Při aktuálním omezení bez textu se údaje dodají přímo strukturovaně |
| 2 | Získat klíč psychoonkologického screeningu. Do té doby neodvozovat střední úzkost nebo depresi z číselného skóre. Umět předat potvrzené `moderate_anxiety` / `moderate_sadness` | Mapování v `meddi/clinical_rules.py` a vstupní adaptér; původní skóre uchová `meddi/form.py` | §4 psychická zátěž; pro význam stupně CTCAE v5, s. 109. Ověřit C08 i nízká skóre, negace a žádost o psychologa, která sama neprokazuje 2. stupeň |
| 3 | Navrhnout a klinicky ověřit mapování slovních odpovědí `bol_klouby` a `brneni` na symptom a jeho stupeň. Pro potvrzený 2. stupeň použít obecné existující žluté pravidlo; nepředstírat konkrétní NRS ani jemnou motoriku | Vstupní mapování `meddi/clinical_rules.py`; časový kontext v `meddi/patient_inputs.py`; regresní případy v existujících testech | §4 první odrážka + CTCAE uvedené výše. Součástí musí být vyhodnocení přínosu i nových vyšších výsledků, nikoli jen opravených lower |
| 4 | Pro kožní obtíže potvrdit typ a stupeň: paronychie / ruka-noha / jiný problém. Obecné `kuze=1` nepřekládat automaticky na konkrétní diagnózu | Vstupní údaje a mapování `meddi/clinical_rules.py` | §4 první odrážka. Dodat typ obtíže nebo schválené mapování obecného stupně; ověřit 009-C08 a 017-C03/C04 i negativní případy |
| 5 | Předávat délku zácpy, čas poslední průjmovité stolice, schopnost udržet tekutiny a konkrétní odpověď na SOS. Samotná nespokojenost s analgezií není údaj o účinku SOS | `meddi/patient_inputs.py` / vstupní formulář; existující pravidla v `meddi/clinical_rules.py` a `meddi/triage.py` | Přesné kombinace §3, zácpa §4 a interval 12 h v §5. Testy mají pokrýt neznámý údaj a hranice, ne pouze potvrzenou hodnotu |
| 6 | Dodat stav řešeného problému a lékařský plán s časem: co tým posoudil, zda se aktuálně stav zlepšil, změnil či zhoršil. Oddělit samotnou existenci kontaktu od klinického rozhodnutí | `meddi/patient_inputs.py`, posouzení typických pravidel v `meddi/triage.py` | §5 a §6.3. Mentor musí upřesnit, kdy přetrvávající 2. stupeň nebo NRS 4–6 při řešeném stavu může být green. Tvrdé minimum §3 nesnižovat |
| 7 | Domluvit přesnou operacionalizaci obecných trendů, obvyklého tlaku a nejistoty. Uchovat aktuální řadu měření jako důkaz | `meddi/patient_inputs.py`, pravidla/politika v `meddi/triage.py` | §5 a §6.1, §6.4. Nevymýšlet nový práh typu „každé tři rostoucí váhy = yellow“, „106/66 = hypotenze“ nebo „každá obava = střední úzkost“ |

Zpracování zpráv je další samostatná etapa podle §6.2. V této etapě musí
zůstat odložené podle pokynu týmu; proto nelze slibovat opravu všech textových
případů jen doplněním dalších podmínek do `clinical_rules.py`.

### Důležitá kontrola navržené obecné gradace

Research zkusil nad všemi 171 vstupy jednoduchý návrh: `brneni` nebo
`bol_klouby` s indexem 1 označit jako potvrzený 2. stupeň. Tento návrh
**nebyl implementován** a index sám není validovaným klinickým stupněm.

Výsledek pokusu: **130 shod, 27 lower, 14 higher** oproti současným
132 / 30 / 9. Opravil by 002-C12, 016-C02 a 016-C04, ale přidal by pět
vyšších výsledků: 002-C13, 002-C14, 002-C15, 002-C16 a 005-C04.
První skupinu reference považuje za stav známý týmu, druhou za mechanickou
bolest po práci na zahradě. Z toho neplyne právo tyto případy natvrdo vyjmout;
plyne potřeba validovat mapování a kontext. Předchozí tvrzení, že u kloubní
bolesti pomůže pouze NRS, bylo příliš úzké: obecné pravidlo 2. stupně je
relevantní, jeho nasazení však vyžaduje vyřešit tyto souvislosti.

### Všech 30 lower: údaj, konkrétní změna a zdroj

Ve sloupci barva je aktuální výstup → reference. Zkratky §§ odkazují na
`pravidla_triaze.md`, nikoli na nově vymyšlenou sadu podmínek.

| Check-in | Barva | Co doložit nebo změnit | Přesná opora / hranice závěru |
| --- | --- | --- | --- |
| ONC-002-C05 | green → yellow | `neuropathy_persistent_between_cycles`; přetrvávání je nyní pouze ve zprávě | §4 neuropatie; více samostatných hlášení brnění samo nedokládá, že mezi nimi nikdy nevymizelo |
| ONC-002-C12 | green → yellow | Potvrdit jemnou motoriku ze zdrojového popisu, nebo ověřit mapování obecného 2. stupně z dotazníku | §4 neuropatie a první odrážka; obecné omezení ADL nevydávat za konkrétní jemnou motoriku |
| ONC-004-C08 | green → yellow | Potvrzený střední stupeň úzkosti / klíč převodu 6/10 | §4 psychická zátěž; existující pravidlo funguje po dodání vstupu, viz výše |
| ONC-007-C06 | green → yellow | Stupeň otoků a potvrzené hodnocení trendu; nyní třídenní přírůstek pouze 0,9 kg | §4 otoky nebo >2 kg / 3 dny; §6.1 trend. Rýhy od ponožek nepovažovat automaticky za ověřený 2. stupeň |
| ONC-007-C07 | green → yellow | Stav přetrvávajícího problému, otoky/trend; nyní přírůstek v okně 0,8 kg | §4, §6.1 a §6.3; delší řadu nepřepsat na nesplněný přesný třídenní práh |
| ONC-007-C08 | green → orange | `orthopnea`; informace o polštářích je v textu. Třídenní přírůstek 1,4 kg sám práh nesplňuje | §3 oranžová / Dýchání; po kontrolním dodání ortopnoe pravidlo vrací orange |
| ONC-008-C03 | green → yellow | `polydipsia` a `frequent_urination` vedle známé glykémie 17,8 | §4 glykémie >15 se žízní a častým močením; samotná glykémie není celá kombinace |
| ONC-008-C06 | green → yellow | `constipation_days=3`, nyní pouze ve zprávě | §4 zácpa ≥3 dny; trvalá zácpa v nabídce neudává přesný počet dní |
| ONC-008-C07 | green → yellow | Pokračování stejné epizody a její potvrzená délka | §4 zácpa ≥3 dny; po doložení trvání lze počítat čas, nelze automaticky slepovat všechny výskyty |
| ONC-009-C04 | green → yellow | Kvalifikovaně posoudit 2. stupeň zvýšeného tlaku vůči výchozímu stavu | §4 obecný 2. stupeň, §5 antiangiogenní léčba; CTCAE v5 s. 145 je doplňková opora. 152/95 nesplňuje orange 160/100 a zatím jsou jen dvě vysoká měření |
| ONC-009-C08 | green → yellow | Typ/stupeň kožního problému a pokračování známé toxicity | §4 první odrážka, §5 kontext; `kuze=1` neprokazuje samo typ obtíže |
| ONC-009-C12 | green → yellow | Hypotenzi se závratí potvrdit v kontextu obvyklého tlaku, pauzy a antihypertenziv | §4 ortostatická hypotenze a §5 pauza léčby; 106/66 samotné nestačí ke klinickému závěru |
| ONC-010-C03 | yellow → orange | `cannot_keep_fluids`; po dodání se aktivují dvě existující orange podmínky | §3 oranžová / Příjem a Zvracení; minimální příjem neznamená automaticky neudržení tekutin |
| ONC-010-C10 | green → yellow | Potvrdit klinickou psychickou zátěž a potřebu návaznosti před další léčbou | §4 psychická zátěž, §5–6 kontext. Úzkost 2/10 ani samotná běžná obava nejsou ve zdroji jednoznačný práh yellow |
| ONC-011-C05 | yellow → orange | `new_only_liquid_food` + `pain_uncontrolled`; dotazník potvrzuje tekutou stravu, ale ne konkrétní účinek morfinu | §3 oranžová / Příjem a tekutiny; `spokojenost=Ne` může mít více důvodů |
| ONC-011-C08 | yellow → orange | `cannot_keep_fluids`, případně potvrzené přetrvávání silné bolesti po SOS | §3 oranžová / Příjem nebo Bolest; NRS 7 bez účinku SOS nesplňuje samo uvedenou kombinaci |
| ONC-011-C09 | orange → red | Ověřit konkrétní red příznak nebo rozhodnutí klinika; automatické pravidlo pro „oligurii po cisplatině = red“ ve zdroji není | §3 červená / Zvracení a Dehydratace/oběh. Kontrolní dodání nízké diurézy, sníženého příjmu a závratí ponechalo orange; nevymýšlet >10 h anurie ani nemožnost pít |
| ONC-014-C02 | green → yellow | `constipation_days=4` ze strukturovaného potvrzení | §4 zácpa ≥3 dny; počet je nyní jen ve zprávě |
| ONC-014-C07 | green → yellow | Potvrdit psychický stupeň / potřebu podpory; zachovat ESAS depresi 8 jako zdrojové skóre | §4 psychická zátěž, §5 paliativní kontext; ESAS číslo není přímo CTCAE stupeň |
| ONC-014-C08 | green → yellow | `caregiver_exhaustion`; zátěž patří pečující osobě | §4 vyčerpání pečující osoby a §6.7; nezaměňovat únavu pacienta a pečujícího |
| ONC-014-C09 | orange → red | `slow_breathing` / `unresponsiveness` / nová nápadná spavost; nyní jsou v textu | §3 červená / Opioidy, případně Neurologie. Kontrolní dodání pomalého dýchání vrací red. §5 paliativní péče nesnižuje povinnost pomoci |
| ONC-016-C02 | green → yellow | Ověřené mapování střední artralgie s omezením činností na obecný 2. stupeň | §4 první odrážka a CTCAE uvedené výše; není nutné vymýšlet NRS, ale nelze ignorovat nové vyšší výsledky z plošného mapování |
| ONC-016-C03 | green → yellow | Potvrzená střední úzkost nebo smutek; klíč použitého screeningu | §4 psychická zátěž. Dvě skóre 6/10 a zájem o psychologa jsou důležité nálezy, ne doložený automatický převod |
| ONC-016-C04 | green → yellow | `medication_nonadherence`; případně ověřené mapování 2. stupně artralgie | §4 vynechávání léků / první odrážka; nepřipisovat vynechání léčby všem bolestem kloubů |
| ONC-016-C05 | green → orange | `hopelessness` ze skutečného výroku; dotazník suicidalitu popírá | §3 oranžová / Psychika a §6.2; beznaděj je samostatná podmínka vedle kladné suicidální odpovědi |
| ONC-016-C07 | green → yellow | Stav otevřeného psychického problému a aktuální posouzení, nikoli slepé přenesení dřívější orange | §4 psychická zátěž, §6.3; aktuální check-in psychický stupeň neobsahuje |
| ONC-017-C03 | green → yellow | `paronychia_limits_activity` s doloženou lokalizací a omezením | §4 paronychie; obecná kožní otázka sama neurčuje typ, aktuální popis nehtu je textový |
| ONC-017-C04 | green → yellow | Potvrdit pokračování stejného nehtového problému a současný stupeň | §4 a §6.3; z absence nové zprávy neodvozovat uzdravení ani novou eskalaci |
| ONC-018-C03 | green → orange | Zachytit rozpor zprávy s formulářem a doptat se na počet nad normál | §3 oranžová / Průjem a §6.2–4. Šest celkových stolic nevydávat za šest nad normál. Potvrzený probíhající průjem při irinotekanu dává aspoň yellow; potvrzených 4–6 nad normál orange |
| ONC-018-C04 | green → yellow | `hours_without_diarrhea` nebo právě probíhající průjem a stav epizody | §5 irinotekan: <12 hodin bez průjmu; součet stolic za 24 h tento interval neurčuje |

### Všech 9 higher: co lze a nelze bezpečně snížit

| Check-iny | Výstup a příčina | Konkrétní další krok a opora |
| --- | --- | --- |
| ONC-004-C07 | yellow → referenční green; aktuálně mírný průjem při imunoterapii | §4 průjem na imunoterapii dává typickou yellow, reference používá stav po léčbě a zlepšení (§6.3). Potřebujeme posouzený aktuální stav a upřesnění, kdy má tento kontext změnit barvu |
| ONC-011-C01, ONC-011-C10, ONC-011-C13 | yellow → green; afty omezující jídlo, u C10 navíc NRS 4–6 | §4 příjem/bolest versus §6.3. Doložit lékařský plán a aktuální zlepšení; samotné probíhající ozařování nebo existence analgetik není uvedená automatická výjimka |
| ONC-014-C06 | yellow → green; NRS 4 po zlepšení po úpravě analgezie | §4 bolest NRS 4–6, §6.3 aktuální stav. Reference používá klinický kontext, ale text nedává algoritmus, kdy trvající NRS 4 přebít na green. Vyjasnit s mentorem |
| ONC-018-C06, ONC-018-C08, ONC-018-C12, ONC-018-C13 | yellow → green; tři zvýšená měření, pacient má hypertenzi a podobné výchozí hodnoty | §4 ≥3 měření, §5 obvyklý chronický stav a §6.3. Doplnit schválený obvyklý tlak a klinický plán. Nevypínat celé tlakové pravidlo a nevymýšlet vlastní toleranci rozdílu |

Úvod pravidel výslovně rozlišuje tvrdá minima §3 a klinický úsudek v §4–6.
Proto devět higher automaticky neznamená devět chybných číselných podmínek.
Je třeba odlišit barvu závažnosti od toho, zda už tým upozornění přijal;
potlačení duplicitní notifikace samo neprokazuje nižší závažnost.

### Hotový návrh ověření dalších změn

Před každou implementací z výše uvedených kroků připravit malou cílenou změnu
a ověřit původní neshodu i kontrolní případy: C08 střední úzkost proti nízkým
skóre; nový 2. stupeň proti známému řešenému stavu; aktuální varovný příznak
proti odeznělému; pečující proti pacientovi; celkový počet stolic proti změně
nad normál; budoucí léčbu a zásah týmu proti časově dostupnému kontextu.
Zachovat maximum tvrdých minim a reference vždy až v hodnoticí větvi.

Skutečně provedené kontroly tohoto research kroku: úplné přehrání main.py,
audit 39 neshod, 24 kontrolních dosazení a experiment mapování stupně na celé
sadě. Nové jednotkové testy ani změny aplikačního kódu nejsou výsledkem tohoto
kroku; výše uvedené testovací body jsou požadavky pro navazující implementaci.

Výchozí kód výzkumu je commit `0420073`. Kontrola úplnosti ověřila, že rozpis
obsahuje všech 39 aktuálních neshod, součty 30 lower / 9 higher a všech 24
kontrolních dosazení; lokální odkazy výzkumu existují. `git diff --check`
prošel. Změny tohoto kroku jsou pouze `docs/tasks.md` a výslovně požadované
vymezení výstupních polí v `AGENTS.md`; zbývající neznámé údaje nebyly domyšleny.

Pull a příprava publikace 17. 10. 2026: začleněn `ddb4789` s výkladem
výstupních polí v AGENTS.md a rozborem neshod. Konflikt v tabulce úkolů
vyřešen zachováním obou sad záznamů: vzdálený research a lokální sjednocení
backendu jsou odlišné dokončené kroky. Prošlo 543 testů, Ruff, offline CLI
meddi.pipeline nad syntetickými ukázkami a načtení jeho výstupního JSON;
23 místních odkazů ověřeno. Linux, bez živého LLM a bez Windows.


Sloučení main → web a napojení triáže 17. 10. 2026: fetch přinesl
`origin/main=ebdc475`; merge commit `272581c` má rodiče `d6e7cc0` a `ebdc475`.
Předchozích 34 změněných/nesledovaných souborů bylo zazálohováno do
`/tmp/rakathon-web-merge-aqw8wivi/` a do stash
`codex-preserve-web-before-main-merge`, který zůstává zachovaný.
Konflikty dokumentace a form.py vyřešeny se zachováním obou modulů;
`answer_colors` je kompatibilní pohled nad přípravou odpovědí z main,
nikoli nová implementace barev. Z obnoveného lokálního flow zůstaly společné
potvrzení a opravy; aktuální optimalizace a úplný katalog z main zachovány.

Nové změny: `web/triage.py`, `web/app.py`, `web/patient_report.py`, obě
stránkové šablony, `_triage.html`, `triage.css`, `tests/test_web_triage.py`,
rozšíření `tests/test_survey_recovery.py` a README/týmové zápisy. Formulář
ukazuje backendové barvy a důvody po návratu extrakce a po potvrzení; uložený
check-in obsahuje celé vyhodnocení včetně intake. Report má poslední výsledek
a historii s důvody, zdroji a problémy k dořešení. Starší záznamy vyhodnocuje
sdílené jádro s kontextem dostupným v jejich čase; nebere maximum celé historie.
Zelené minimum s neúplným posouzením se navenek nezobrazuje jako zelená.

Ověření: `uv --cache-dir /tmp/rakathon-uv-cache run --locked --offline pytest -q`
— 583 testů prošlo. Ruff check celého projektu a format --check devíti
dotčených Python souborů prošly. Regrese ověřují rozdíl červené barvy možnosti
a oranžové triáže pro pocit 5, budoucí léčbu, odeznělé staré varování, neúplnost,
backendovou shodu, HTML escaping a uložení nálezu mimo dotazníkové odpovědi
s načtením reportu po ztrátě relace. Všech 14 zdrojových profilů v reportu
vrátilo HTTP 200 s triáží; všech 29 zdrojových JSON má nezměněný SHA-256
před/po této kontrole a nevznikl žádný pacientský soubor. Git diff --check
a kontrola konfliktových značek prošly. Linux / Python 3.12, bez volání LLM;
Windows ani klinické ověření se neprováděly. Manifest a lock beze změny.

Zbývá klinické review a úplná orchestrace K2–K10, zejména urgentní vyhodnocení
před dalším cíleným LLM voláním a úplné ukládání událostí před LLM. Původní
barvy odpovědí a samostatný měřicí přehled zůstávají doplňkovým pohledem,
nejsou výslednou triáží. Kromě vyžádaného merge commitu nebyl vytvořen další
commit ani push; navazující úpravy jsou v pracovní kopii.


Vrácení poslední opravy reportu 17. 10. 2026 na pokyn uživatele:
odstraněn otevřený přehled historických rizik, výběr check-inu, nové mapování
barev měření a související změny textů a tři testy. Obnoven stav po původním
napojení triáže: poslední check-in a sbalená historie. Merge 272581c,
předchozí propojení triáže i cizí rozpracované změny zachovány; data se neměnila.
Změněné soubory: web/triage.py, web/patient_report.py, report.html,
_triage.html, triage.css, tests/test_web_triage.py, tests/test_patient_report.py
a docs/architecture.md, docs/decisions.md, docs/tasks.md.
Ověření: uv --cache-dir /tmp/rakathon-uv-cache run --locked --offline pytest -q
— 583 testů prošlo; Ruff check, formát čtyř dotčených Python souborů a
git diff --check prošly. Linux, bez sítě; žádný commit ani push. Původní
problém skrytí historického rizika při neúplném posledním záznamu tím zůstává
nevyřešený.

Vyřešení konfliktů origin/main → web: v app.py zachované require_basic_auth
z web a state z main, v obou dokumentech zachovaný obsah obou stran.
Balicí skript rozšířen o MASTER runtime a prompty (55 souborů).
Testovací klienti původních webových testů používají syntetické Basic Auth;
produkční ochrana ani autentizační testy se neobcházejí. Jeden převzatý test
čte JSON explicitně jako UTF-8 pro Windows, dvě textové konstanty mají
závorky kvůli Ruff ISC004 beze změny obsahu. 681 testů prošlo s pracovní
--basetemp v .scratch (výchozí systémový pytest adresář byl nepřístupný),
Ruff celého projektu a format --check pěti upravených Python souborů prošly.
Rozbalený ZIP ověřil import aplikace, 401 bez hesla a 200 pro formulář,
statiku i report se syntetickým heslem. Bez LLM volání, commitu či nasazení.

Triáž pouze podle pravidel 17. 10. 2026: odstraněn fallback přebírající
answer.color do závažnosti, zachované zobrazovací non_green_answers.
Nejistota konkrétních klinických pravidel a žluté předání nepokrytých
aktuálních údajů zůstávají; žádný návrat k neurčeno. U doloženého průjmu
při irinotekanu se neznámá doba bez průjmu označí jako předběžná žlutá,
nikoli jako potvrzené trvání <12 h. Zdroj: pravidla_triaze.md §5 a §6.4;
klinické lidské ověření není tímto nahrazené. Zvýšení rules_version 4→5
vynutí přepočet uložených webových hodnocení ze zmrazených vstupů.
Windows/Python 3.12: 708 pytest testů prošlo (--basetemp v .scratch),
včetně 20 variant změny/vypnutí barevných metadat, časové nejistoty,
hranice 12/24 h a přepočtu starých hodnocení. Ruff celého projektu,
formát šesti změněných Python souborů a git diff --check prošly.
Strukturovaný replay bez referencí a LLM: 171 check-inů, všechny mají barvu;
42 green, 113 yellow, 11 orange, 5 red. Žádný důvod unassessed_answer:*
a žádné neurčeno. Nejde o klinickou validaci nebo měření shody s referencí.
Azure ZIP znovu vytvořen a rozbalený ověřen (import, přihlášení, formulář,
statika, report). Bez commitu, pushe a nasazení; lokální .env.example beze změny.

Zprávy pacienta 17. 10. 2026: nová meddi/messages.py spojuje stávající
MasterExtractor a API klient s aktuálním check-inem, léčbou a stejným jádrem
pravidel. LLM vrací pouze fakta s citacemi a subjektem; nekalkuluje barvu.
Python detekuje explicitní popření proti příznaku i nesoulad přesných počtů
s volbou rozmezí, zachová horší variantu a vrací otázky k upřesnění. Nepřítomná
položka dotazníku není popřením. Samotný počet stolic neznamená počet nad
normál/24 h. Trvající „od vcera“ zachová příznak, nikoli vymyšlenou délku;
časové údaje mimo podporované okno zůstávají nevyhodnocené. Kód nerozšiřuje
klinické prahy. Zdroje: pravidla_triaze.md §3–6, zejména §6.2–4; README §6.
Historický report má explicitní POST pro extrakci s Basic Auth a tokenem;
ukládá původ a fakta do pracovní kopie, originály nemění. Opakované GET/POST
použijí uložená fakta bez dalšího volání, změněný zdroj se odmítne a lze
zpracovat znovu. Živé MASTER kontakty se uloženým výsledkem se neextrahují
duplicitně. Doptání se zobrazí, odpovědi z budoucnosti ani z referencí nevznikají.
CLI --with-messages zapíná extrakci, výchozí porovnání zůstává bez sítě.
Přes uv přidáno tzdata (pyproject.toml i uv.lock) pro Europe/Prague.
Ověření Windows / Python 3.12: 736 pytest testů prošlo (28 nových pro zprávy),
Ruff check . a formát 9 dotčených Python souborů prošly, git diff --check
prošel. API nahrazené falešným extraktorem, včetně ONC-018-C03; ověřen payload
stejného klienta a striktní schéma. Živý model se nevolal: místní LLM klíč
není nastaven. Kontrolní replay s prázdnou falešnou extrakcí: 96 neprázdných
a 75 prázdných zpráv, neztratilo se žádné známé strukturované klinické minimum.
Nejde o ověření kvality modelu či shody s referencí. Azure ZIP má 56 souborů,
rozbalený prošel importem, přihlášením, formulářem, statikou a reportem.
Bez commitu, pushe a nasazení. Přetrvání DATA_DIR na Azure a úplné klinické
pokrytí textu zůstávají otevřené; cizí změny v .env.example zachované.

Oprava výchozího CLI a diagnostiky zpráv 17. 10. 2026: reprodukováno
ONC-018 --with-messages bez místního klíče: 0 complete / 8 failed / 5 bez
zprávy, původní barevné výsledky zůstávaly jako záložní výpočet. Chyběla
místní llm_intake/.env a proměnná MEDDI_LLM_API_KEY; v Azure klíč nastavený byl.
main.py nyní zahrnuje zprávy automaticky, --with-messages je kompatibilní
alias a --without-messages výslovná offline baseline. Stav zprávy je v každém
řádku a souhrnu bez --details. Při selhání výpis označuje záložní výsledek,
uvádí chybějící konfiguraci a proces vrací 1; při úspěchu 0.
Stávající Azure LLM konfigurace byla bezpečně doplněna do llm_intake/.env,
před zápisem ověřeno ignorování Gitem, existující soubor by se nepřepisoval.
Žádná tajná hodnota nebyla vypsaná ani přidána do sledovaných souborů.
Jedno živé ověření ONC-018-C03 získalo diarrhea.episodes=6 (approximate,
od vcera) a weakness; výsledná žlutá je již založená na pravidle irinotekanu,
nikoli jen na nezpracované zprávě. Baseline a přesné okno 24 h se nevymýšlely.
Následně skutečný běžný běh main.py ONC-018 s 8 API extrakcemi dokončen
s kódem 0: complete=8, failed=0, not_present=5. C02 a C07 se změnily ze
žluté na zelenou; C03 zůstává předběžně žlutá s konkrétním klinickým důvodem.
Reference zůstaly jen v porovnání, model dostával pouze zdrojové zprávy.
Windows/Python 3.12: 740 testů prošlo (4 nové kontroly výchozího běhu,
změny barvy, explicitní offline varianty a chyby klíče), Ruff celého projektu,
formát čtyř změněných Python souborů a git diff --check prošly.
Úspěch 8 extrakcí není úplná klinická validace. Bez commitu, pushe a nasazení.

Webový průchod po upřesnění uživatele 17. 10. 2026: pacient nejprve vybere
jeden ze čtyř dotazníků (výchozí Nežádoucí účinky), projde celý formulář podle
pořadí a podmínek a teprve pak může napsat závěrečnou zprávu nebo ji přeskočit.
Změny: llm_intake/dialogue.py, web/app.py, web/export.py, index.html,
tests/test_questionnaire_web.py, aktualizované test_web.py/test_survey_recovery.py
a týmová dokumentace. Dřívější webový MASTER vstup a limit šesti otázek
nahrazeny; MASTER CLI zůstává kompatibilní. Zpráva se extrahuje stejným API,
fakta vyhodnocuje stejné jádro pravidel, neotevírá se další formulář.
Prázdná zpráva ani přeskočení nevolají API; odpovědi se neslepují do zprávy.
Zdroj pořadí a větvení: dotazniky_definice.json, pole otazky/podminka.
Ověření Windows/Python 3.12: všech 751 pytest testů prošlo, včetně 11 nových
kontrol všech čtyř úplných formulářů, více než šesti otázek, podmíněných větví,
přeskočení zprávy, jejího vlivu na triáž, chyby API a opravy rodiče po zprávě.
Extrakce v těchto testech nahrazená syntetickým klientem, živý model nevolán.
Ruff check ., formát dotčených Python souborů a git diff --check prošly.
Azure ZIP znovu vytvořen (56 souborů) a po rozbalení ověřen import,
401 bez hesla, 200 s heslem pro formulář, statiku i report.
Bez nových závislostí, commitu, pushe a nasazení; trvalé úložiště Azure
zůstává dříve otevřeným bodem.
