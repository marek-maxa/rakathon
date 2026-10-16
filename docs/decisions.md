# Rozhodnutí

Minimální propojení intake a triáže: `evaluate_intake` převádí pouze potvrzený
celkový pocit a NRS. CLI zobrazí známou minimální barvu a neúplnost posouzení;
jiné otázky zatím nemají mapování. Bez dalšího LLM volání a bez nových závislostí.

MASTER QUESTION (16. 10. 2026): tým požaduje otevřený popis stavu a následný
výběr jen potřebných otázek, použitelný také pro pozdější kontrolu parametrů.
Zdrojovou zprávu zpracovávat společně se `zprava_pacienta`; zachovat čas a autora.
Rozpracovaný [návrh propojení](master-question.md) odděluje fakta, odpovědi,
prozatímní riziko a plán kontrol. Klinická interpretace nejistoty a konkrétní
intervaly vyžadují upřesnění; nejde zatím o implementovanou pipeline.

Technický návrh: zachovat oba aktuální moduly a přidat adaptér a katalog vazeb,
zatím bez RAG. Vyšší úroveň z možných podložených interpretací počítá kód;
nezapisuje se jako pacientem potvrzená horší hodnota. Bezpečnostní kontrolu
neomezovat vyhledanými otázkami a nečekat na dokončení rozhovoru při známém
tvrdém pravidle. Důvody a zdroje jsou v návrhu.

| Datum | Rozhodnutí | Důvod |
| --- | --- | --- |
| 2026-10-16 | Ponechat katalog a zprávu ve stejném uživatelském vstupu, katalog před proměnlivým textem | Při měření přesun katalogu do samostatné systémové části způsobil u jednoho citlivého syntetického screeningu HTTP 400 content_filter, původní i opravené uspořádání prošlo. Zachovat dotazníkový kontext a možnost opakovat statický prefix. Blokace má vlastní hlášení, chybná úvodní analýza uchová zprávu se stavem processing_error |
| 2026-10-16 | Zmenšit reprezentaci MASTER a omezit cílené příklady, zachovat všech 49 témat a přesné možnosti | MASTER vynechá pouze mechanická metadata, poznámku formuláře předá jednou a celý katalog tvoří statický prefix. Cílené volání má nejvýše 3 příklady stejné otázky/typu, API JSON je kompaktní. Po limitu kontaktu se další cílená extrakce nevolá; neomezujeme pokrytí filtrem klíčových slov nebo top-k |
| 2026-10-16 | Měřit tokeny z API a přesnost na plně označené syntetické sadě | Volitelný on_usage callback ukládá jen počty a dobu, bez textů a klíčů. Oddělit chybějící metriky od nuly, záchyt minimálních témat od nepovolených přiřazení, ověřovat negaci a subjekt. Cache měřit přes cached_tokens; slevu a latenci neslibovat z jediného měření. Klinické ověření je samostatné |
| 2026-10-16 | Úplný katalog 49/49 otázek místo prvních šesti témat; klíčová slova, aliasy a kontext v question_topics.json | Celý katalog a aktuální balíčky otázek jsou v promptu; fakt vrací topic_ids omezené dynamickým enumem. Kód mapuje přesná ID a zachová pořadí i podmínky; žádné top-k nebo filtrování jen doslovnými slovy. Chybějící položka katalogu vyvolá chybu. Úplnost struktury nezaručuje sémantickou úplnost LLM; tu ověřuje oddělená syntetická regrese |
| 2026-10-16 | Oddělit rozpoznaná témata od rozpočtu dotazování; zbývající otázky exportovat jako dialogue.pending_topic_ids | Všechna rozpoznaná fakta a kandidáti zůstávají v paketu i při limited; pacient se nezahltí automatickým kladením všech otázek. Popření a potíže pečujícího nevyvolávají cílený dotaz pacientovi; neznámé pojmy zůstávají viditelné |
| 2026-10-16 | Propojit MASTER se stávajícím Intake přes seed původních zpráv a oddělené MasterDialogue | Úplná odpověď jde k potvrzení, neúplná k doptání. Zachovat skutečné otázky, autory, ID a dostupnost zdrojů; nepředstírat, že MASTER odpověď vznikla na cílený dotaz. Původní API i kolegovo napojení cíleného CLI na triáž zůstávají zachované |
| 2026-10-16 | Výchozí limit kontaktu 6 zahrnuje MASTER, doptání, potvrzení i opravy; limit doptání parametru zůstává 2 | Omezení zátěže a opakovaných odmítnutí bez vynucování hodnoty. Limity lze nastavit; po vyčerpání limited, nepotvrzené hodnoty zůstávají návrhy. Jde o prototypovou politiku, nikoli klinicky schválené časování |
| 2026-10-16 | Obecná extrakce každé další slovní odpovědi a přidání nových témat po uzavření aktivní relace | Nové potíže se nesmějí ztratit kvůli cílené otázce ani porušit její rozpracované pořadí. Naléhavost a reakce na riziko nadále patří do nezávislé integrace; MASTER dialog tuto bezpečnostní větev neimplementuje |
| 2026-10-16 | Rozhraní modulu pro pipeline: find_question, QuestionnaireFlow.for_targets a create_targeted_session | Zjednodušení integrace cíleného dotazování na parametr bez nutnosti znát interní ID dotazníku; jednotná fasáda balíčku llm_intake; pro 49 otázek zatím ponechán přímý katalog bez RAG/embeddingů; srovnávací benchmark neproběhl, validace schématu je nezávislá na vyhledávání |
| 2026-10-16 | MASTER extraktor vytěžuje fakta, kandidátní otázky vybírá kód přes dosavadní katalog | Samostatný prompt, striktní schéma a pět syntetických příkladů; LLM nevrací triáž ani potvrzení. Zachovat neznámá témata a neurčený subjekt, neptat se pacienta automaticky na potíže pečujícího nebo popřený příznak. Zatím šest témat, kandidáti nejsou hotový plán |
| 2026-10-16 | Sdílet HTTP transport Client.send a tvorbu striktního požadavku s oběma extraktory | Zachovat dosavadní autentizaci a chybové stavy bez kopie klienta. Modelu pro MASTER poslat pouze text, otázku a autora; zdroj, ID a simulovaný čas zůstanou v aplikační obálce |
| 2026-10-16 | Sdílený balíček otázky a možností pro model, katalog, příklady i export; volitelné /moznosti | Tým chce usnadnit pacientovi odpovídání a přitom přesně zachovat definice. Příklady odkazují ID místo kopií textů. Výlučné „žádné“ nelze kombinovat s účinky; popis barev se modelu nepředává |
| 2026-10-16 | Pořadí a podmínky řídit QuestionnaireFlow ze zdrojového JSON; rozlišit celý formulář a cílený vstup | Tým požaduje původní větvení a budoucí kontrolu jednoho parametru. Cílený vstup nevyplňuje rodiče mimo rozsah, uvnitř rozsahu platí potvrzené podmínky; nevyřešené větve zůstávají viditelné |
| 2026-10-16 | Nový pipeline paket llm_intake / v1 vedle původního intake v2 | Normalizované hodnoty, potvrzení a zdroje bez barev; odmítnutý návrh není aktuální odpověď. MASTER extraktor, karta, časování a triáž zůstávají oddělené následující úkoly |
| 2026-10-16 | Nejbližší krok MASTER QUESTION omezit na samostatný kontrakt zprávy/faktů a první katalog v LLM části | Tým vyvíjí LLM nezávisle; triáž, karta a plánovač jsou nyní pouze kontext budoucího zapojení. Zachovat intake v2, intervaly, zdroj a nejasnost; nepokryté pojmy nezahazovat. Paket faktů má vlastní schema_version=1 a potvrzení unconfirmed přidává aplikace; obecný extraktor bude další krok |
| 2026-10-16 | Python 3.12 + uv | Společný základ pro Python/ML na Linuxu i Windows |
| 2026-10-16 | Obecné AGENTS.md + startovní prompt v README; práce podle docs/tasks.md | Jedno zadání pro libovolné agenty bez dalších šablon |
| 2026-10-16 | documents/ pro zdroje, docs/ pro týmové zápisy | Podklady lze rovnou vkládat bez správy indexu |
| 2026-10-16 | Přesné dodatečné kopie podkladů archivovat v documents/_duplicates/; zpřesnit tři neurčité názvy | Obsah ověřen porovnáním bajtů a SHA-256; vratný úklid bez mazání zdrojů, mapování v docs/vyber-tematu.md |
| 2026-10-16 | Tým vybral MEDDI ONCO Challenge | Výslovné rozhodnutí týmu; aktivní zadání v docs/challenge.md |
| 2026-10-16 | Ostatní podklady přesunout do documents/archive/, výběr tématu a staré úkoly do docs/archive/; odstranit tři znovu ověřené duplicity a lokální cache | Nový začátek na pokyn týmu, zachování původních podkladů a předchozí práce; nahrazuje rozhodnutí o uchování _duplicates/ |
| 2026-10-16 | Odstranit předem zvolené runtime knihovny, ponechat Python 3.12 + uv, pytest a Ruff | Bez implementace nemají ML/HTTP knihovny využití; závislosti přidávat podle konkrétní potřeby |
| 2026-10-16 | Nejprve data a jeden průchod v čase, potom implementace po domluvených krocích | Architektura je návrh k diskusi; MEDDI JSON zatím chybí, framework ani AI poskytovatel nejsou vybrané |
| 2026-10-16 | První prototyp bude CLI, prioritu mají data a funkčnost; frontend a nasazení odkládáme | Výslovná představa týmu, snadné testování a přehlednost |
| 2026-10-16 | Pacientská karta s vývojem v čase, LLM pro personalizované dotazy a strukturované zpracování odpovědí | Směr určený týmem; podoba historie, hranice rozhodování LLM, časování a schéma zůstávají k diskusi v docs/architecture.md |
| 2026-10-16 | První CLI používá simulovaný čas a předem zaznamenané odpovědi | Výslovná odpověď týmu; umožní opakovatelné přehrávání, odpovědi na nové otázky se nesmějí domýšlet |
| 2026-10-16 | MEDDI balíček je dostupný v rakathon_meddi_onco_data/ | Potvrzeno týmem a lokálně ověřeno 14 pacientů / 171 check-inů; reference zůstávají oddělené, podmínky pro LLM popisuje README balíčku, oddíl 6 |
| 2026-10-16 | Veškerou triáž určuje náš kód; LLM pouze extrahuje informace pro rozhodování | Výslovná volba týmu. Kód vyhodnotí také kontext, trendy a nejistotu a určí úroveň, další krok, kontakt a upozornění; LLM nadále personalizuje formulaci otázek |
| 2026-10-16 | První implementace: jeden triage.py, JSON vstup a barva s důvody; jen horečka při chemoterapii, absolutní saturace, pocit a bolest | Tým chce malý celek k review před LLM a širším CLI. Neúplný vstup se neoznačuje zeleně; prokázaná barva zůstává minimem a omezený rozsah je součástí výstupu |
| 2026-10-16 | Kód triage.py a jeho JSON rozhraní jsou anglicky | Výslovný požadavek týmu na čitelnost; hlavní funkce evaluate_triage, barvy green/yellow/orange/red; aktuální kontrakt v architecture.md |
| 2026-10-16 | Odstranit vlastní validaci a obsluhu výjimek z prvního prototypu | Tým upřednostňuje jednoduchý výzkumný kód pro připravený vstup; zachovat rozhodovací pravidla a rozlišení neznámých údajů |
| 2026-10-16 | Jedna funkce na kritérium; výsledná závažnost je maximum skóre | Požadavek týmu na jednoduchou modularitu. Skóre 1–4, None pro nevyřešené kritérium; výstup ukazuje skóre místo textových důvodů |
| 2026-10-16 | Izolovaný llm_intake/ pro jednu otázku, pacientovo potvrzení a opravu | Samostatná práce na pokyn týmu, bez zásahů do karty, triáže a definic; stav a potvrzování spravuje Python, export má schema_version=1 |
| 2026-10-16 | Výchozí kandidát gpt-6.1-sol, Chat Completions přes dodanou OpenAI kompatibilní bránu | Oficiální podpora Structured Outputs a kompromis schopností/nákladů; zdroje v llm_intake/README.md. Nejde o změřené prvenství na MEDDI; klíč zůstává v prostředí, živé volání zatím neověřeno |
| 2026-10-16 | Pacient odpovídá vlastními slovy; definované možnosti a barvy zůstávají interní | Upřesnění týmu: LLM přiřazuje význam odpovědi k možnosti, pacient potvrzuje jen slovní znění; kód připojí barvu odpovědi, další triáž zůstává samostatná. Technický výpis CLI vyžaduje --debug |
| 2026-10-16 | Brána používá hlavičku api-key a deployment gpt-6-1-sol-dz-eu | 401 reprodukováno u Authorization i Ocp-Apim-Subscription-Key; po api-key následovalo 404 DeploymentNotFound pro obecné ID. Přesný deployment dodal tým a živé volání uspělo. Lokální .env opraven bez změny klíče |
| 2026-10-16 | Nejasná odpověď vyvolá cílené doptání ve stejném LLM volání; historie obsahuje i otázky, export v2 | Reakce na opakování dotazu u „ne, nejde mi spat“. Výchozí limit dvě doptání, pak unresolved; nevynucovat vymyšlenou volbu. Počty doptání a odmítnutí měří kód |
| 2026-10-16 | RAG, embeddingy a práh podobnosti zatím odložit | Všechny možnosti jedné otázky už jsou v kontextu; chybí informace od pacienta. Nejprve nezávislé označené případy pro správnost a počet nutných dotazů; podobnost není kalibrovaná pravděpodobnost správné odpovědi. Technické zdroje a odůvodnění v llm_intake/README.md |
