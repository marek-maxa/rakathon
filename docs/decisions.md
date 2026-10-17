# Rozhodnutí

Minimální propojení intake a triáže: `evaluate_intake` převádí pouze potvrzený
celkový pocit a NRS. CLI zobrazí známou minimální barvu a neúplnost posouzení;
jiné otázky zatím nemají mapování. Bez dalšího LLM volání a bez nových závislostí.

| Datum | Rozhodnutí | Důvod |
| --- | --- | --- |
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
| 2026-10-16 | Nejmenší webový prototyp: Flask HTML formuláře bez JavaScriptu, tři ukázkové otázky | Odpovídá požadovanému toku bez nové frontendové vrstvy; stav je pouze v paměti, potvrzené odpovědi může pacient upravit |
| 2026-10-16 | Web je vícekrokový formulář, nikoli chat; chyby patří do samostatného přístupného upozornění | Zpětná vazba k prototypu: otázky a ovládací prvky mají být hlavní obsah, technické chyby se nesmějí tvářit jako konverzační bublina; nepoužívaný chatový skript odstraněn |
| 2026-10-17 | Společné HTTP Basic Auth pro všechny Flask požadavky, údaje z prostředí, při chybějící konfiguraci odmítnout přístup | Výslovný požadavek týmu na heslo před nasazením dema; bez nové závislosti a vlastního Nginxu, Azure musí vynucovat HTTPS. Nejde o individuální účty pro klinický provoz |
| 2026-10-17 | Nasadit současný formulář a reporty na existující Azure App Service, jeden Gunicorn worker | Pokračování nasazení na pokyn týmu; ZIP zahrnuje pouze potřebný runtime a syntetické vstupy, reference a tajemství zůstávají mimo. Nové nezapojené MasterDialogue moduly neaktivujeme. Existující HTTPS Only neměníme |
