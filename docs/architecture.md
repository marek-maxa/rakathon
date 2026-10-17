# Architektura a spuštění

Python 3.12 + uv. Web používá Flask/Jinja, HTML formuláře a Plotly;
JavaScript zobrazuje průběh zpracování a brání opakovanému odeslání.
Manifest a lock jsou v kořeni repozitáře. Triážní jádro nemá vlastní runtime
závislosti. Požadované budoucí chování popisuje [plán](meddi-onco-plan.md).

## Implementovaný stav

Aktuální funkční kontrola proti oficiálním zdrojům a zamýšlené doplnění
dema jsou v [plánu](meddi-onco-plan.md#funkční-kontrola-proti-zadání),
pořadí práce D1–D4 v [úlohách](tasks.md#priority-do-dokončení-mvp).
Demo má společné kontroly pacienta a týmu s ručním termínem a volitelným
opakováním, viditelnou neodpovědí a aktualizací po potvrzené odpovědi.
Lékařský přehled a stručný souhrn doplňují léčbu, doložené trendy a časovou
osu. Průchod času sám nespouští novou klinickou triáž; samostatné SMTP
připomenutí není klinické vyhodnocení neodpovědi.

| Část | Co existuje | Co chybí pro cílový tok |
| --- | --- | --- |
| `llm_intake/` | Obecná extrakce, katalog 49 otázek, cílený MASTER, společné potvrzení/opravy a volitelný checkpoint před cílenou extrakcí | Výběr priorit podle rizika, trvalé obnovení |
| `meddi/` | Sdílená deterministická pravidla, normalizace, validace, zdrojované důvody a výstupní politika | Úplné vstupy a klinické mapování, obecná nejistota/trendy, karta a orchestrace |
| `web/export.py`, `web/triage.py` | Export vybraných ověřených měření s původem, živé trendy stávajícího adaptéru a zdrojovaný kontext léčby | Úplný registr měření/epizod a skutečného podání léčby |
| `web/app.py`, `web/portal.py` | Pacientský portál, autor pacient/pečující, MASTER i přímé kontroly/měření/nálezy ze zprávy, opakování dle ručního plánu, potvrzení a naléhavá instrukce | Individuální oprávnění, obecný klinický plánovač |
| `web/patient_store.py` | Pracovní kopie pacienta, atomické přidání potvrzeného check-inu a zdrojově vázaná uložená extrakce historické zprávy | Sjednocení projekce s událostmi, průběžné revize a podpora více procesů |
| `web/event_store.py` | SQLite deník původních zpráv před LLM, stabilní ID, dohledatelné opravy a deduplikace | Trvalé výsledky zpracování a obnova dialogu K2b; úplná historie měření/revizí K2c |
| `web/patient_report.py`, `web/clinical_view.py`, `meddi/status.py` | Prioritní přehled s filtry, souhrn/context/trendy/časová osa, ruční plán a záznam kontaktu; úplná historie a grafy ve druhé úrovni | Obecné epizody, klinicky převzatý souhrn, skutečné předání/převzetí |
| `notifications/` | Samostatný formulář pro pevný testovací e-mail a SMTP transport | Napojení na triáž, adresáti/priorita, spolehlivé předání a převzetí |
| `main.py`, `meddi/messages.py` | Strukturovaný replay, volitelná extrakce historických zpráv, konflikty a návrhy doptání, reference oddělené | Úplné klinické pokrytí šesti situací, reakce na odpovědi, intervence a souhrny |

Obecný klinický plánovač, samostatný strukturovaný formulář měření/přeměření
a skutečné předání monitorovacímu centru nejsou implementované.

## Moduly a datové cesty

| Modul | Rozhraní / odpovědnost |
| --- | --- |
| `llm_intake.master` | `MasterExtractor`, `analyze_message`: zpráva → fakta a kandidáti otázek |
| `llm_intake.core`, `flow`, `dialogue` | Jedna odpověď, větvení a MASTER kontakt; [kontrakt](../llm_intake/MASTER_CONTRACT.md) |
| `meddi.form` | `prepare_checkin`: původní formát → normalizované odpovědi a zdrojové barvy |
| `meddi.patient_inputs` | `build_triage_inputs(patient, checkin)` → prepared/context/observations dostupné k check-inu |
| `meddi.pipeline` | `evaluate_contact(packet, patient_snapshot=None, *, context=None, now=None, prepared_checkin=None)` |
| `meddi.messages` | `evaluate_message_checkin(patient, checkin, *, extract=None, analysis=None)`: zpráva a původní check-in přes stejné jádro; bez vymyšlených odpovědí |
| `meddi.triage`, `clinical_rules`, `answer_coverage` | Sdílený výpočet pravidel, pokrytí a nevyřešených vstupů |
| `meddi.disposition` | `resolve_disposition`: výsledná úroveň, krok, kontaktní instrukce a doporučení |
| `meddi.validation` | Domény, typy a jednotky; neplatný vstup není negativní nález |
| Kořenový `triage.py` | Kompatibilní vstupy delegující do `meddi/`; ploché API má omezený rozsah čtyř kritérií |
| `meddi.loader` | Načtení původních pacientů; reference načítat pouze v hodnoticí větvi |
| `web.event_store` | `EventStore(path).accept(owner_id, contact_id, message, *, question_id=None, corrects_event_id=None)` → uložená zdrojová zpráva; `get(owner_id, event_id)` a `contact_messages(owner_id, contact_id)` → čtení deníku |

Živý web:

```text
MessageEvent → EventStore.accept (commit původní zprávy)
             → MasterDialogue.start/submit → obecná extrakce
             → checkpoint → assess_contact → evaluate_contact → evaluate_checkin
             → minimum 3/4: paused → naléhavá instrukce ve webu
             → jinak: cílená extrakce → průběžné assess_contact
```

Po `confirm_all()` se výpočet zopakuje a export s celým hodnocením uloží.
`MasterDialogue` sám klinická pravidla nezná. Volitelný callback předaný
webem vyhodnotí obecnou extrakci dřív, než může začít cílené volání.

Historický check-in:

```text
build_triage_inputs → evaluate_checkin → resolve_disposition
```

Strukturovaná cesta zůstává offline. `evaluate_message_checkin` připojí
jednu extrakci původní zprávy, nebo ověří a znovu použije `analysis` shodnou
s originálem. Spojí připravené odpovědi, měření, časově dostupný kontext
a zprávu přes `evaluate_contact(..., prepared_checkin=prepared)`.
Prázdná zpráva nevolá API; chyba zachová strukturované minimum a viditelný
stav selhání. Konflikty vracejí `follow_up_questions`, nikoli domyšlené odpovědi.
Report provede LLM jen po explicitním POST s tokenem; GET používá uložená fakta.
Klinická úplnost šesti situací zůstává M3.
Podrobnosti triáže jsou pouze v [backendu](backend.md).

### Měření a trendy M2

`assess_contact` nejprve deterministicky normalizuje aktuální kontakt přes
`evaluate_contact(packet, now=at)`. Jeho vybraná přesná měření promítne do
dočasného check-inu a `build_triage_inputs` doplní stávající trendy hmotnosti,
opakovaného tlaku a soběstačnosti spolu s kontextem léčby. Druhé vyhodnocení
dostane jen tento zdrojovaný `context`/`observations`; staré vitální hodnoty
se nepředávají jako dnešní. Oba průchody jsou lokální, bez dalšího LLM volání.
Klinické prahy ani léčebná pravidla se v M2 nemění. Kontext zachovává zdroj
léků/cyklů; chybějící podklad pro podání není negativní příznak. Plný registr
skutečného podání a rozlišení plánu/D1 zůstává K3.

`meddi_record(packet, completed_at, *, include_drafts=False, assessment=None)`
zapisuje měření z `assessment.triage_inputs.observations`, nikoli novou
interpretací textu. Při předání hodnocení ověřuje shodu pacienta, kontaktu
a intake. Bez hodnocení slouží dosavadnímu náhledu odpovědí bez měření.
Podporuje teplotu, SpO₂, systolický/diastolický tlak, glykémii, hmotnost a tep.
Normalizace nově přijímá i `weight_kg` a `pulse_bpm`; existence měření sama
nepřidává klinické pravidlo pro jeho vyhodnocení.

Každá hodnota v `vitalni_funkce` má `hodnota`, `jednotka`,
`zdroj=zprava_kontaktu`, `observed_at`, `available_at` a `podklady` s hodnotami,
ID zprávy, doslovným důkazem a stavem potvrzení. Zdroj se nevydává za přímý
odečet přístroje. Při současném rozporu je `hodnota=null`, všechny podklady
zůstanou zachované a graf/trend nevybírá svévolně jeden bod; triáž dál vidí
všechny zprávy. Novější hodnota nahrazuje starší podle společného adaptéru.
Tato projekce obsahuje aktuálně vybrané hodnoty; úplná historie jednotlivých
měření uvnitř kontaktu včetně nahrazených zůstává v intake, nikoli jako více
bodů grafu. Staré uložené check-iny se zpětně nedoplňují.

`zprava_pacienta` obsahuje pouze úvodní sdělení. `zdrojove_zpravy` zachovává
samostatné MASTER/cílené odpovědi, autory, otázky a časy; `vyplnil` vychází
z autora úvodní zprávy (`pacient`/`pecujici`/`tym`/`neznamy`). Export podporuje
pečujícího v kontraktu i ve formuláři.
Ukládá se projekce téhož konečného hodnocení v čase `evaluated_at`.
Datum/čas check-inu jsou v Europe/Prague a čas dostupnosti má pásmo.
Adaptér trendů respektuje i explicitní čas měření a jeho dostupnost;
graf používá datum pozorování, pokud je známé. Pro Windows je přidané `tzdata`.
Bez explicitního času pozorování zůstává výchozím čas přijetí zprávy;
relativní historický čas se automaticky neodhaduje.

Tvar původních dat: [README balíčku §5](../rakathon_meddi_onco_data/README.md#5-datový-slovník).
Trend a kontext: [pravidla triáže §4–6](../rakathon_meddi_onco_data/docs/pravidla_triaze.md).

## Doporučení a směrování M4

`meddi.routing.timed_route(color, at, ...)` určuje kontakt a termín podle
pravidel triáže §2 a §5. Je čistá funkce bez systémových hodin, LLM nebo
odesílání zpráv. `resolve_disposition(..., at=None, palliative_care=None)`
ji používá až po určení výsledné úrovně; směrování nemění klinické minimum,
barvu, podklady ani úplnost. `at` přijímá čas s pásmem nebo ISO řetězec;
uvnitř se převádí na `Europe/Prague`. Bez času zůstává obecný kontaktní
pokyn a `routing.time_status=unknown`, žádný smyšlený kalendářní termín.

Centrum je otevřené Po–Pá **7:00 včetně až 15:30 nezahrnuto**. MVP používá
běžný týdenní kalendář; státní svátky a výjimky konkrétního pracoviště nejsou
dodané a nejsou součástí výpočtu. Před provozním použitím je nutné kalendář
a kontakty potvrdit. Termíny vždy patří ke konkrétnímu času hodnocení:

| Úroveň | Směrování |
| --- | --- |
| 1 | Záznam týmu v přehledu, další sledování; bez termínu zásahu |
| 2 v pracovní době | Centrum, vyřízení do 15:30 následujícího pracovního dne |
| 2 mimo pracovní dobu | Nejbližší otevření centra v 7:00, vyřízení do 15:30 tohoto pracovního dne; při zhoršení sloužící lékař, při ohrožení 155 |
| 3 v pracovní době | Lékař MOÚ / telekonzultace do 2 hodin; při nedostupnosti centra nebo po zavření ihned služba |
| 3 mimo pracovní dobu | Sloužící lékař MOÚ 724 590 848 ihned |
| 4 vždy | 155 / urgentní příjem ihned, požadavek upozornit tým nejpozději do 15 minut |

Dvouhodinová a patnáctiminutová lhůta se počítají jako skutečně uplynulý čas,
včetně přechodu mezi letním a zimním časem. Přednost mají už doložené zvláštní
pokyny §4: `symptomatic_hyperglycemia` ještě dnes (mimo dobu centra služba),
`persistent_neuropathy` a `cisplatin_tinnitus` před další aplikací/dávkou.
Budoucí termín podání se neodhaduje a systém léčbu ani dávkování nemění.

Doložené `context.palliative_care=True` směruje úroveň 2/3 na 24h linku
vlastního paliativního týmu / hospice podle plánu péče, při nedostupnosti 155.
U červené zůstává primární neodkladná pomoc; přání se předají týmu a nejsou
důvodem pomoc vynechat. Číslo hospice se nevymýšlí. `patient_inputs` tuto
hodnotu odvodí pouze z přesného strukturovaného záměru `symptomatická
paliativní péče`; obecný paliativní záměr systémové léčby nebo samotný text
dříve vyslovených přání není doklad zapojení hospice. Zdroj je v
`context_sources.palliative_care`.

Strukturované hodnocení používá datum/čas check-inu v Praze, živý kontakt
`evaluated_at`, ploché `evaluate_triage(data, at=...)` dodaný čas. Historický
report doplní i starému uloženému hodnocení směrování k původnímu času;
nepoužije dnešní hodiny ani novější léčebné údaje a původní JSON nepřepisuje.
Nové `routing` nese `as_of`, `within_working_hours`, `next_center_open_at`,
`contact_code`, `phone`, `response_due_at`, `team_notify_by` a zdroj pravidel.
Časy jsou ISO s offsetem, pro UI jsou doplněné odpovídající textové popisky.
Naléhavá instrukce P0, konečný výsledek, report a kartička ukazují kontaktní
pokyn a lhůtu ze stejného hodnocení. Lhůty jsou požadavky, nikoli doklad
skutečného předání nebo převzetí; fronta a doručování zůstávají mimo M4.

## Web a ukládání

| Cesta | Význam |
| --- | --- |
| `/` | Úvodní volba rozhraní Pacient / Lékař |
| `/patient` | Bez profilu demo přihlášení kódem; s profilem portál, MASTER a cílené kontroly, GET i POST |
| `/patient/demo` | Oddělené demo účty; POST zvolí syntetický profil a vyčistí předchozí rozhovor |
| `/patient/logout` | POST odhlásí demo profil a zneplatní jeho paměťový rozhovor a odesílací tokeny |
| `/patients/<patient_id>/report` | Report profilu z pracovní kopie nebo původních dat |
| `/team` | Demonstrační přehled požadavků z posledního hodnocení každého pacienta |
| `/patients/<patient_id>/team-action` | POST s session tokenem: ruční plán existující kontroly nebo záznam kontaktu do pracovní kopie |
| `/patients/<patient_id>/checkins/<checkin_id>/analyze-message` | Explicitní POST pro extrakci historické zprávy, kontrola session tokenu a zdroje |
| `/assets/plotly-<version>.min.js` | Lokálně poskytovaný Plotly skript |
| `/static/<path:filename>` | Styly a skripty webu |

Úvodní volba vede pacienta na `/patient`, lékaře na `/team`. Pacientská
navigace neodkazuje přímo do zdravotnického reportu, lékařský přehled vede
do detailů. Nenápadný odkaz „Změnit rozhraní“ v patičce označené Demo
vrací na úvod bez zrušení rozpracovaného
rozhovoru. Jde o oddělení navigace dema, nikoli kontrolu přístupu;
všechny cesty nyní chrání společné heslo dema (Basic Auth). Individuální
produkční role a ověřené účty implementované nejsou.

Původní dropdown nahrazuje obrazovka demo přihlášení: pole `patient_id`
je přístupový kód syntetického profilu (např. `ONC-001`), nikoli heslo či
produkční autentizace. Seznam fiktivních účtů je jen v odděleném demo ovládání.
Odhlášení a změna účtu zahodí paměťový stav i vlastnický klíč rozhovoru;
staré odesílací tokeny nepatří nové session. Uložené check-iny zůstávají.
Skutečné účty/oprávnění a pozvánky zůstávají mimo MVP.
Výchozí MASTER zní „Jak se dnes cítíte?“.
Web používá `bulk_confirmation=True`: návrhy se kontrolují společně,
`revise(index)` otevře opravu a zneplatní závislé odpovědi, `confirm_all()`
potvrdí jen vyřešené návrhy. Fakta z obecné extrakce tím nejsou samostatně
potvrzená. Web má `MAX_QUESTIONS=6` a používá cílený režim:
MASTER vybírá konkrétní relevantní otázky, nikoli celé dotazníky. Již sdělené
údaje se využijí přes `Intake.seed`; úplná odpověď jde do společné kontroly,
chybějící rozlišení vyvolá doptání. Zachovají se původní otázky a zdroje,
nejde o domyšlené pacientské odpovědi.

Implementovaný [pacientský portál](meddi-onco-plan.md#must-have-pacientský-portál)
spojuje MASTER, poslední uložený stav s časem a doporučením, vlastní údaje,
poslední tři kontroly a malý seznam sledovaných položek. `build_portal`
používá `checkin_assessments` stejně jako report; budoucí check-iny a budoucí
splnění nezobrazuje. Neprovádí LLM ani zápis při GET. Prázdný profil nemá
zelený výsledek. Historický stav je výslovně označený, rozpracovaný běžný
výsledek se nezveřejňuje před potvrzením a P0 má přednost před starým stavem.

`portal_controls` v pracovní kopii pacienta obsahuje nejvýše šest položek
pro nové sledování: `id`, `kind` (`question`/`measurement`/`finding`), `label`,
`source_checkin_id`, `created_at`, `completed_checkin_id` a případně doložené
`due_at`. Výchozí návrh vychází z nejnovějšího dostupného check-inu:
nejvýše tři nezelené odpovědi, pozitivní pacientské nálezy uložené extrakce
a až tři podporovaná měření do společného limitu šest. Nález bez mapování
na otázku se doptá doslovným popisem; nevytváří smyšlenou volbu dotazníku.
Zdrojová barva zde vybírá položku ke sledování, neurčuje klinickou úroveň.
První tři položky jsou viditelné, ostatní rozbalitelné. Bez plánu se interval nevymýšlí.
Při potvrzeném appendu se evidence atomicky uloží spolu s check-inem;
aktualizovaná je jen položka s novou uloženou odpovědí či měřením z doby
od vzniku kontroly. „Aktualizováno“ neznamená odeznění klinického problému.
Neznámá/rozporná hodnota kontrolu nesplní. Obecný plánovač se tím nezavádí.

Lékař zadává `due_at` v Europe/Prague a volitelně `repeat_hours`, poznámku
pro pacienta a existující `control_id`. `record_team_action` ukládá plán
atomicky; `requested_at` odděluje starou odpověď od nově požadované.
Potvrzená odpovídající odpověď/měření obnoví termín jen při explicitním
intervalu: čas odpovědi + interval. Bez něj je kontrola jednorázová.
`schedule_history` uchovává časově dostupné verze plánu a splnění pro
historické zobrazení; budoucí změna neovlivní dřívější pohled.
Splatná neodpověď se ukáže v obou rozhraních a filtru týmu „Po termínu“.
Sama nezmění klinickou barvu. `demo_team_events` uchovává ruční plány
a záznamy kontaktu; nejde o klinické odeznění ani odeslanou notifikaci.

`web.clinical_view.doctor_view` sestavuje souhrn bez LLM nad stejným
hodnocením: změna naléhavosti, citace a autor, režim/D1 s označením
„podle záznamu cyklu“, souběžné léky, dostupné laboratoře, až tři trendy
a krátká časová osa. Číselné minigrafy používají skutečné hodnoty; slovní
odpovědi zůstávají slovní. Kontext je k času hodnocení, ruční plán k času
otevření. Zdrojové ID/datum zůstává dostupné. `/team?view=urgent|overdue|review`
a `q` filtrují stávající pohled; nevytvářejí novou klinickou klasifikaci.
Úplná historie je rozbalovací; Plotly se načte až při jejím otevření.

POST `follow_up=<id>` validuje vlastní sledovanou položku a otevře přímo
její otázku nebo dotaz na nové měření s jednotkou. Nedovolí nahradit
rozpracovaný kontakt ani nezpracovanou přijatou zprávu. Odpověď zachová
`source=targeted_answer`, skutečnou otázku a autora; další extrakce, P0,
potvrzení, triáž, export a report používají stávající cestu.
`MasterDialogue(follow_up_topic="dotaznik/otazka")` přidá pouze tento
existující cíl i tehdy, když obecná extrakce nevybere téma. Přesná validní
odpověď na něj může dokončit sběr i bez obecných faktů; nejde o výjimku pro
prázdnou MASTER zprávu. Nevyřešené další vstupy a známá minima zůstávají.
U měření se údaj a jednotka extrahují ze skutečné odpovědi, ne z historie.

Funkční průchody ověřují `tests/test_patient_portal.py`,
`tests/test_doctor_followup.py` a `tests/test_mvp_scenarios.py`.
Responzivita byla zkontrolovaná v Chrome při šířce 1440 a 390 px bez
vodorovného přetečení. Prohlížečový nácvik prošel plán → neodpověď → pacient
→ potvrzení → další explicitní termín → přehled týmu; také odložené grafy,
bez JS chyb. LLM byl nahrazený a SMTP blokované.
Samostatně je povinné [zrychlení LLM](meddi-onco-plan.md#must-have-rychlost-llm-pro-prezentaci),
podle změněné priority až poslední implementační krok po funkcích a přípravě M5.
Současný klient vybírá deployment přes `MEDDI_LLM_MODEL` a poskytuje
`Client.on_usage` s dobou volání a tokeny; to je základ pro porovnání.
Menší model ani nové nastavení uvažování nejsou tímto plánem zavedené.

`QuestionnaireFlow(targets=...)` zahrne jen vybrané otázky a jejich podmíněné
potomky. Rodiče mimo rozsah nevyplňuje. Nové téma může přidat další relevantní
otázku, ne celý formulář. Rozpočet kontaktu je 6, limit doptání parametru 2;
nevyřešené údaje a kandidáti zůstávají v paketu. Oblasti v UI jen seskupují
otázky ze zdrojových dotazníků, neznamenají jejich úplný průchod.

`dialogue.mode=targeted_from_message` zachovává úvodní aktuální nález i při
pozdější mírnější volbě; pravidla dostanou oba podklady téhož kontaktu.
Explicitní klinické uzavření opravy/odeznění zůstává K4/K7.

### Naléhavá instrukce P0

Web předává `checkpoint(packet) -> bool` při `MasterDialogue.start/submit`.
Callback po obecné extrakci zavolá `assess_contact`. Při minimu orange/red
uloží `safety_notice` do paměťové session a při prvním naléhavém pokynu nebo
zvýšení z oranžové na červenou pozastaví kontakt (`paused`,
`external_checkpoint`) před navazující cílenou extrakcí. To platí také pro
novou odpověď a opravu. Stejný již zobrazený pokyn nevyžaduje opakované
pokračování; zůstává viditelný. Ostatní kontakty pokračují bez přerušení;
zobrazovací barvy, nejistý nebo cizí subjekt samy instrukci nevytvářejí.

Pacient ihned vidí samostatné „Naléhavé doporučení“ s doporučením a kontaktem
ze stejného backendu, bez konečného výsledku triáže. Nemusí nic potvrdit ani
uložit. Výslovný POST `continue` zavolá `resume()`, které dokončí odložený
seed/odpověď bez opakování obecné extrakce a bez přidání dalšího zdrojového
sdělení. Jde o pokračování v paměti procesu, nikoli obnovu K2b. Callback
ani Flask closure se do dialogu neukládá.

Známá instrukce je oddělená od rollbacku rozpracované odpovědi: chyba LLM,
ukládání nebo otevření opravy ji neschová ani nesníží dosavadní červenou.
Nově doložené minimum při konečném potvrzení se zachytí před zápisem, takže
instrukci nezablokuje ani selhání exportu. Pokračování je volitelné a UI
výslovně říká, že doplnění nesmí odložit pomoc. Konečný výsledek zůstává až
po potvrzení a úspěšném uložení; nový výslovný restart založí nový kontakt.
Rozhodnutí uživatele a hranice jsou v [rozhodnutích](decisions.md#bezpečnostní-výstup-k4m4).

### Technický průchod M3

Kladná MASTER odpověď („dobrý/dobře/dobre“) se zachová jako slovní
`overall_feeling`. Pro přesnou krátkou odpověď na skutečnou MASTER otázku
má `analyze_message` úzkou zálohu při prázdném výsledku extraktoru; chyba API
ji nespustí. Obecná fráze nevyplňuje ostatní příznaky ani číslo škály.
`MasterDialogue` nevolá seed pro celkový pocit bez přesného čísla, ale nabídne
jedinou původní otázku `pocit` (1–5). Po skutečné potvrzené cílené odpovědi
ve stejném kontaktu pipeline eviduje původní slovní fakt v `clarified_facts`
s vazbou na zdroj odpovědi. Originál zůstává v intake. Nejistota, neznámý
subjekt, jiné potíže a přesné rozporné hodnoty se takto neodstraňují.

U obecného „špatně/blbě/nic moc“ se také nabídne původní škála bez odhadu
čísla. Po skóre 3/4 bez konkrétních potíží následuje otevřená žádost o popis,
nikoli okamžité uzavření sběru. „Dobře“ a jeho běžná parafráze s následným
skóre 1/2 nepotřebují tuto další otázku; skóre 5 zachovává původní cestu
k naléhavé pomoci podle pravidel §3 / Oranžová / Celkový stav.

`dialogue.message_specificity` zaznamenává `needs_details`, důvod, počet
pokusů a ID zpráv s doplněním. Je to indikátor dostatečnosti popisu pro
dialog, nikoli odhad klinické závažnosti. Ve stavu `needs_description` je
`active=None` a otázku poskytuje `MasterDialogue.next_question`. Odpověď
projde běžnou obecnou extrakcí a checkpointem před případným cíleným LLM;
nová témata se vrátí do existujících flow. Není to uměle vyplněná otázka
dotazníku. Originál, autor a skutečná otázka zůstávají ve zdrojových událostech
a doplnění je viditelné ve společné kontrole.

Doptání respektuje rozpočet 6 a `max_clarifications` (výchozí 2). Pokud
pacient potíže neupřesní, skončí sběr jako `unresolved/insufficient_detail`
nebo `limited/question_budget`; stávající pipeline zachová neúplnost
k lidskému posouzení. Samotné skóre 4 nezavádí novou klinickou barvu.
Zdrojem doptání jsou pravidla triáže §6.4 a zadání PDF s. 5 a 7.

Nález bez otázky není automaticky nevyhodnocený: pipeline porovná původní
`unmapped_concepts` s validovanými vybranými vstupy jádra a vykáže zbývající
`unresolved_concepts`. Pokud je celé `open_findings` způsobeno jen těmito
zpracovanými vstupy, nepřidá falešné `intake_not_complete`. Neznámé nebo
nejisté nálezy zůstávají k review. „Nově/nove“ a „náhle/nahle“ označují
aktuálně hlášený nález, nikoli odhadnutou délku jeho trvání. „Právě/prave“
a „právě teď/prave ted“ se stejně jako „nyní“ zpracují jako aktuální údaj;
při chybějícím čase pozorování zůstává časem přijetí zprávy. Složený
historický výraz se nerozpoznává jen podle prefixu; originál se zachovává.

`master.analyze_message` neotevírá horečkovou otázku pro přesnou jistou
teplotu v °C pod prvním intervalem jejích zdrojových možností. Dolní mez
se čte z definice otázky, nejde o nový klinický práh. Fakt zůstává v triáži,
exportu a historii; nevymýšlí se index „37,0–37,9 °C“ pro hodnotu 36,8 °C.
Nejistá hodnota, jiná jednotka, rozsah nebo další vyšší hlášená teplota
se tím nevyřeší a nadále mohou vyvolat upřesnění. Zdroj:
`dotazniky_definice.json`, `nezadouci_ucinky/teplota`; klinické úrovně dál
určuje jen sdílené jádro podle pravidel. Tato oprava platí pro nové
zpracování, staré uložené intaky se automaticky znovu neextrahují.

Nenápadné textové tlačítko pod otázkou „Nejste [jméno] a odpovídáte za
pacienta? Klikněte zde.“ jedním kliknutím přepne na pečujícího; ve stejném
místě nabídne návrat k odpovídání za sebe. Checkbox ani samostatné potvrzení
volby nejsou potřeba. POST `set_author` volí `patient`/`caregiver` před novou odpovědí. U již
přijatého nezpracovaného vstupu změnu odmítne. MASTER pro pečujícího má
vlastní skutečné znění; cílené otázky zachovávají původní význam a UI je
výslovně rámuje jako odpovědi za pacienta. Subjekt potíží je nadále samostatný
údaj. Web i historická cesta předávají extraktoru slovník podporovaných
klinických polí včetně měření, nikoli pacientskou kartu nebo reference.

`patient_inputs` odvozuje `palliative_care` jen z explicitního strukturovaného
`lecba.zamer` s původem tohoto pole; neinterpretuje volné poznámky. Jde o
výchozí kontext karty, nikoli nový registr změn léčby. Sdílená výstupní politika
pro paliativní 2/3 odkazuje na 24h paliativní tým/hospic, při nedostupnosti
155; úroveň 4 ponechá okamžitou neodkladnou pomoc. Nevymýšlí telefon týmu.
Zdroj: pravidla triáže §5 / Paliativní péče. `care_context` zachovává podklad
směrování i pro přepočet; verze politiky je 6. Dříve vyslovená přání jsou
zvlášť dostupná zdravotníkovi s upozorněním ověřit platnost; nejsou vstupem
LLM ani automatickým důvodem snížit úroveň.

`tests/test_mvp_scenarios.py` ověřuje celý webový tok, uložení a stejné
hodnocení v reportu/přehledu, šest situací, mezní a negativní protějšky,
zlepšení v čase, autory a selhání. Model je v těchto testech nahrazený.
Omezená živá kontrola syntetických zpráv doplňuje ověření extrakce; lokální
výstup je v ignorovaném `.scratch/m3-live-extraction.json`. Nenahrazuje
nezávislé klinické převzetí ani plošnou evaluaci skrytých pacientů.

M1 používá `_clinical_card(patient, assessments)` jako společný pohled nad
posledním výsledkem `checkin_assessments`. Kartička nahoře v reportu a na
`/team` ukazuje stejný check-in, čas, verzi pravidel, důvod, krok a kontakt.
Krátký souhrn skládá šablona z kroku a důvodu s nejvyšší úrovní; další důvody
a zdroje jsou dostupné v detailu. Jde o důvody současného hodnocení, nikoli
nový registr klíčových/varovných nálezů nebo výpočet trendu.

Přehled načítá pracovní kopie stejným adaptérem jako report. Zahrne pacienty,
jejichž poslední hodnocení má `upozornit_tym`; řadí je červená → oranžová →
žlutá a v rámci úrovně od nejstaršího check-inu. Neúplnost ani předběžný důvod
samy nepřidávají další prioritu. Starší červená není aktuálním požadavkem,
pokud poslední hodnocení požadavek nemá. Ostatní pacienti a prázdné profily
zůstávají dostupní v rozbaleném seznamu.

Předání je viditelně simulované. Přehled nemá frontu automatického předání ani převzetí,
vlastní úložiště ani další LLM volání. Kontakty a vypočtené termíny podle
času konkrétního hodnocení dodává implementované M4 výše.
Čitelnost a dohledatelnost vychází z [vzorových souhrnů](../rakathon_meddi_onco_data/docs/vzorove_souhrny_pro_lekare.md),
oddíl Zásady; úplný souhrn vývoje podle vzorů ani jeho klinické ověření
tím nejsou hotové.

Relace jsou ve slovníku v paměti procesu, klíčované browser session.
Restart formuláře zachová vybraný profil. Dokončený formulář další změny
odmítne; výslovný restart založí nový kontakt. Restart procesu rozpracované
relace neobnoví. `FLASK_SECRET_KEY` lze dodat prostředím; jinak vznikne náhodně
při startu, takže nejde o konfiguraci trvalého přihlášení.

### Trvalé přijetí zpráv K2a

`web.event_store` je nezávislý na Flasku a používá `sqlite3` ze standardní
knihovny. Web mu předává cestu `DATA_DIR/events.sqlite3`; deník obsahuje
tabulky `contacts` a `message_events`, verzi určuje `PRAGMA user_version=1`.
První použití databázi vytvoří, neznámou verzi odmítne. Transakce,
unikátní ID a cizí klíče chrání příjem a vazbu opravy; spojení se po operaci
uzavře. LLM neběží uvnitř databázové transakce.

Formulář odpovědi nese podepsaný `submission_token` svázaný s browser session,
pacientem, kontaktem, ID odeslání a skutečnou otázkou. Pro cílenou odpověď
obsahuje i kanonické `dotaznik/otazka`. Obnovení stránky ponechá stejný
identifikátor. Zpráva se potvrdí v SQLite ještě před vytvořením LLM klienta;
ukládá se doslovný text včetně okolních mezer, `MessageEvent` s autorem,
zdrojem, otázkou a časem dostupnosti i případné `corrects_event_id`.
Čas dostupnosti je první přijetí serverem v UTC. Čas pozorování se z volného
textu při příjmu neodhaduje. Podepsaný formulář váže i zvoleného autora
`patient`/`caregiver`; změna před novou odpovědí nepřepíše staré události.

`accept` vrací `StoredMessage` se zdrojovým `MessageEvent`, kontaktem,
kanonickým ID otázky a vazbou opravy. Stejné ID a obsah vrátí původní zprávu
včetně jejího času, změna obsahu pod stejným ID se odmítne. Oprava dostává nové
ID a odkaz na původní událost stejného kontaktu; původní text se nepřepisuje.
`contact_messages` vrací pořadí přijetí, nikoli klinický trend.

Při chybě LLM zůstává předchozí dialog i trvalá zpráva. Formulář odliší
uložený vstup od nedokončeného zpracování; umožní zopakovat zpracování stejné
události nebo výslovně založit její opravu. Při chybě zápisu se LLM nespustí
a web netvrdí úspěšné přijetí. Již zpracovaný opakovaný POST neposkytne
odpověď další otázce ani nespustí znovu LLM. Opakování neúspěšného zpracování
zatím může dokončená dílčí LLM volání zopakovat; jejich ukládání patří do K2b.

Deník přežije restart, dialog se zatím neobnoví. Při zachované podepisovací
konfiguraci a cookie web po ztrátě paměti rozpozná starý přijatý POST a odmítne
jej znovu zpracovat jako nový rozhovor. Pro zachování cookie a podpisu mezi
starty je nutný stabilní `FLASK_SECRET_KEY`; bez něj zůstávají data na disku,
ale starý formulář není platný. `owner_id` je vazba browser session,
nikoli autentizace ani oprávnění zdravotníka. Odolnost SQLite příjmu proti
souběhu neznamená bezpečný víceprocesový provoz dialogu a JSON exportu.

Zavedení je aditivní: současné potvrzené JSON working copies zůstávají
beze změny a dál slouží reportu. Staré check-iny se nepřevádějí na domnělé
původní zprávy; zdrojové události se v deníku evidují od zavedení K2a.
Budoucí změny schématu nebo projekce musí mít explicitní migraci. Uložení
události a potvrzeného JSON exportu zatím není jedna společná transakce.

Potvrzení přidá check-in do `data/pacienti/<patient_id>.json`. Flask konfigurace
`DATA_DIR` (z prostředí `MEDDI_DATA_DIR`) mění kořen výstupu; `data/` ignoruje Git. První zápis vytvoří pracovní
kopii z původního syntetického profilu, další přidávají historii. Pacientské ID
pochází z vybraného profilu. Opakované `checkin_id` se podruhé nepřidá.

Zápis serializuje procesový zámek, dočasný soubor a `Path.replace` ve stejném
adresáři. Při chybě lze potvrzení zopakovat. Toto chrání lokální demo v jednom
procesu, nikoli souběh několika serverových procesů. Originální data a CLI
loader se nemění.

Uložený `triage_assessment` obsahuje celý `meddi_contact_assessment/v1`,
včetně intake, důkazů a zmrazených `triage_inputs`. Report při odlišné verzi
pravidel přepočítá uložené vstupy bez použití novější historie; originál na
disku nepřepisuje. Poslední stav vybírá podle času, nikoli nejhorší historické barvy.

## Otevřené integrační mezery

- P0 chrání již rozpoznané minimum. Kvalitu a úplnost extrakce ani klinické
  ověření všech šesti situací nenahrazuje. Instrukce zůstává v paměti;
  úplné průběžné/přerušené revize a obnova po restartu zůstávají K2b/K4.
- K2a ukládá originál před LLM, ale výsledky extrakce a stav dialogu zůstávají
  v paměti. Restart tedy neztratí přijatý vstup, avšak neobnoví rozhovor ani
  průběžnou revizi; to je K2b. Testy `test_web_events.py` rozlišují zachování
  nové zprávy od zachování předchozího dialogu.
- M2 předává pouze trendy existujícího adaptéru. Obecné epizody, expirace
  a interpretace vývoje příznaků v textu zatím nejsou implementované.
- M3 má technické průchody šesti situacemi i běžným stavem. Klinické převzetí
  mentorem a obecné vyřešení O1–O10 tím nejsou hotové. Plný provozní kalendář
  a konkrétní kontakty pracoviště zůstávají P2.
- Historie incidentů není registr aktivních klíčových/varovných nálezů.
  Označení „varovné“ v reportu zahrnuje i žluté historické údaje, a proto
  neodpovídá užšímu týmovému významu aktuálních varovných příznaků.
- `upozornit_tym` je požadovaná akce v datech. Neprokazuje odeslání ani převzetí.
  Chybí trvalá evidence příjemce, priority, termínu, pokusů a převzetí;
  samostatné SMTP demo ji nenahrazuje.
- `web.app` předává explicitní čas hodnocení s pásmem; export a adaptér
  timestampovaných měření jej převádějí do `Europe/Prague`. `disposition`
  a M4 počítají kontakt a termín podle běžného týdenního kalendáře; kalendář
  svátků a výjimek pracoviště zůstává k doplnění a potvrzení.

## Spuštění a kontroly

### Demo a samostatná offline záloha M5

[Prezentační podklad](demo.md) uvádí živý průchod, omezení ověření a návrh
MEDDI/EU integrace. `uv run --locked python -m scripts.build_demo` vytvoří
`dist/demo/index.html` a `results.json`; `--output <adresář>` určí jiný cíl.
HTML má vložené styly, kotvy a nativní rozbalovací detaily; po exportu
nepotřebuje server, JavaScript, síť ani LLM/SMTP konfiguraci.

Vstupy `demo/cases.json` jsou ručně připravené syntetické zprávy/fakty a
případné cílené odpovědi pro šest situací (zadání PDF, s. 9). Export používá
`MessageEvent`, `Fact`, potvrzený `Intake`, `build_pipeline_packet`,
`assess_contact` a `meddi_record`. Po kroku přidá pouze dosavadní záznam
do kopie historie; názvy situací a očekávání nejsou vstupem pravidel.
Výsledek včetně neúplnosti zobrazuje společná šablona `_triage.html`.
Artefakt je výslovně označený jako předpřipravená ukázka s historickými časy,
nikoli živý rozhovor nebo dokončené předání. Nemění aplikaci ani její
chování při výpadku modelu; nezapisuje do pracovních kopií ani originálů.

Export navíc zavolá existující `main.compare_patients(..., with_messages=False)`
a přiloží agregaci strukturovaného replay. Reference jsou jen ve
vyhodnocovací větvi, nikoli v připravených klinických vstupech. Tato agregace
neprokazuje kvalitu extrakce zpráv ani celého produktu a neuzavírá K7/K9.
`tests/test_demo_export.py` ověřuje šest případů, časovou izolaci,
nezávislost na názvech a výstup bez externích volání. Vizuální převzetí
exportu a celý prohlížečový nácvik zůstávají otevřené. Samostatný technický
nácvik formulářových handlerů se skutečným LLM je doložen v demo podkladu;
ověřil běžný stav, konkrétní měření a termín kontroly, P0 a uložení/kartičku
v oddělených průchodech bez zásahu do původních dat nebo nastavení modelu.

### Web a stávající kontroly

Všechny příkazy z kořene repozitáře; syntaxe je společná pro Linux a PowerShell.

```text
uv sync --locked
uv run --locked python -m web.app
```

Web automaticky načte `llm_intake/.env`; existující proměnné prostředí mají
přednost. Používá port 5000. LLM konfigurace a CLI jsou v
[README intake](../llm_intake/README.md); notifikační demo má
[vlastní návod](../notifications/README.md) a při výchozím spuštění stejný port.

Offline kontroly:

```text
uv run --locked python -m pytest -q
uv run --locked ruff check .
uv run --locked python main.py
uv run --locked python main.py --comparison lower --details
uv run --locked python main.py --comparison higher --details
uv run --locked python -m meddi.pipeline meddi/contact.example.json --snapshot meddi/snapshot.example.json
uv run --locked python -m llm_intake --list
git diff --check
```

`main.py` má výchozí offline strukturovanou cestu; `--with-messages` zapne
LLM extrakci. `--without-messages` je explicitní offline varianta.
Chyby zpráv jsou v řádku i souhrnu; při selhání LLM vrací proces 1
a barevný výsledek označuje jako záložní. Reference nikdy nevstupují do modelu.
Ani jedna cesta nenahrazuje evaluaci celého produktu.
Vyšší výsledek není automaticky zbytečná eskalace a `requires_review` zahrnuje
i chybějící podmínky hypotetických pravidel. Testy naléhavého výstupu ověřují
pořadí před cíleným LLM a zachování instrukce při chybě; neprokazují skutečné
doručení klinického požadavku.
`--comparison` filtruje řádky, souhrn stále počítá celou sadu. Testy intake/webu
používají náhrady LLM; SMTP ověřují testy uvedené níže. Živé evaluace jsou
samostatná explicitní volání se syntetickými daty.
Prošlé testy a správné schéma neprokazují klinickou správnost nebo úplnost
extrakce. Testovací výsledky průběžně získávat příkazy, nevést jejich historii
jako součást specifikace.

Testy `tests/test_event_store.py` a `tests/test_web_events.py` ověřují K2a:
čtení v novém Python procesu, souběžné příjmy a opakování, transakční selhání,
příjem před LLM, chybu extrakce, odmítnutí starého/cizího formuláře a opravy.
Používají dočasnou databázi a syntetické zprávy bez sítě. Neověřují obsluhu
živého LLM, klinickou správnost, obnovení dialogu K2b ani provoz ve Windows.

## Nezávislá přijímací sada podle zdrojů

[tests/acceptance_meddi](../tests/acceptance_meddi/README.md) uchovává
syntetické vstupy oddělené od očekávání a zdrojů. Katalog a mapa pokrytí
odkazují na konkrétní části pravidel, strany PDF a slidy PPTX; šest
povinných situací vychází z `documents/MEDDI – MEDDI Onco.pdf`, s. 9.
Nejde o další implementaci triáže ani o již prošlé aplikační testy.

```text
uv run --locked python -X utf8 tests/acceptance_meddi/run.py validate
uv run --locked python -X utf8 tests/acceptance_meddi/run.py self-check
uv run --locked python -X utf8 tests/acceptance_meddi/run.py list --tag required-six
```

Pro hodnocení aplikace musí navazující agent dodat adaptér `module:function`
podle README sady. Adaptér dostává pouze vstup bez ID případu, nesmí číst
reference a před extrakcí filtruje časovou dostupnost. Výchozí běh blokuje
standardní síťové transporty a SMTP; živé LLM vyžaduje explicitní volbu.
Nejasná klinická politika a textové/UI podmínky vracejí lidské review,
nikoli automatický úspěch. Samostatné soubory se záměrně neúčastní běžného
pytestu, dokud není napojen skutečný tok aplikace.

## Heslo dema a balení pro Azure

Web před každým požadavkem včetně `/team`, reportů a statiky vyžaduje
`MEDDI_BASIC_AUTH_USERNAME` a `MEDDI_BASIC_AUTH_PASSWORD` v prostředí nebo
`llm_intake/.env`. Prázdná konfigurace vrátí 503, chybějící/chybné přihlášení
401; není automatická výjimka pro localhost. Heslo je společné pro syntetické
demo, nikoli individuální oprávnění. Mimo localhost používat HTTPS.
Skutečné přihlašovací údaje se do Gitu nezapisují.

```text
uv run --locked python scripts/package_azure.py
uv run --locked gunicorn --bind 0.0.0.0:8000 --workers 1 --timeout 600 web.app:app
```

Gunicorn je pouze pro Linux, Windows používá lokální `python -m web.app`.
ZIP `dist/meddi-azure.zip` obsahuje runtime, šablony/statiku, syntetické
profily, definice a `notifications/mailer.py` pro ruční e-mail; vynechává
`.env`, data working copies, SQLite a reference.
Na serveru nastavit stabilní `FLASK_SECRET_KEY`, obě Basic Auth hodnoty,
`MEDDI_LLM_*` a `MEDDI_DATA_DIR` na trvalé úložiště mimo balík. Jeden worker
je nutný kvůli paměťovému dialogu a zámku JSON zápisu; nejde o víceprocesový
backend. Restart dialog neobnoví, ale SQLite/working copies na trvalém disku
zůstanou. Tato změna připravuje balík a lokální startup; nic nenasazuje ani
neověřuje vzdálený build, tajemství nebo umístění dat v EU. Ověření cílového
prostředí patří do M5/K10, požadavky provozu do zadání P24.

## Ruční e-mail a pacientský výsledek

Karta týmu a detail mají uložený kontakt `kontakt.email`. POST
`/patients/<patient_id>/email` s `action=save_contact` ukládá adresu atomicky
do pracovní kopie; odeslání načítá příjemce z této karty. Podepsaný token
váže formulář na browser a pacienta, session brání opakování posledních
20 úspěšných formulářů. `notifications.mailer` posílá českou pozvánku k vyplnění dotazníku
od ošetřujícího lékaře, bez klinických údajů. Předmět je „MEDDI ONCO –
dotazník od vašeho lékaře“. Text odkazuje slovně do aplikace; veřejná URL
dotazníku zatím není nakonfigurovaná. Stejný text má samostatné SMTP demo. SMTP přijetí není potvrzení doručení ani klinické předání.
Web načítá také `notifications/.env` bez přepsání prostředí.

Pacientský konečný výsledek má výrazný barevný panel, slovní název barvy,
symbol a velké doporučení. Červená má syté výstražné záhlaví. Klinické
texty a výpočet zůstávají společné s backendem.

`tests/test_notifications.py` a `tests/test_patient_mail.py` ověřují SMTP
a formuláře s náhradou transportu; mailové testy používají Basic Auth dema.

## Minimální plánovač notifikací

`notifications.scheduler.NotificationStore` rozšiřuje `DATA_DIR/events.sqlite3`
o tabulky `notification_schema` (verze 1) a `notification_plans`. Migrace je
aditivní a transakční; `PRAGMA user_version=1` zůstává pro původní EventStore.
Jeden plán na pacienta má interval, odstup připomínky, termín a příznaky odeslání.
Příkazy načítají stejné `.env` jako web a podporují `MEDDI_DATA_DIR` / `--data-dir`.

Syntetický příklad časování, nikoli klinické doporučení:

```text
uv run --locked python -m notifications.scheduler schedule ONC-001 --interval-hours 24 --reminder-hours 6
uv run --locked python -m notifications.scheduler list
uv run --locked python -m notifications.scheduler run
uv run --locked python -m notifications.scheduler cancel ONC-001
```

Nejprve uložit kontakt na kartě pacienta. První pozvánka je splatná za zadaný
interval od nastavení. `run` provede jeden průchod a skončí; provozovatel
ho spouští například každou minutu přes cron nebo Windows Task Scheduler,
ze správného pracovního adresáře a stejným datovým adresářem jako Flask.
Samotný web žádný časovač nespouští.

Před odesláním se porovná seznam potvrzených check-in ID s uloženým stavem.
Nový check-in ukončí starou připomínku a další termín nastaví na čas zjištění
plus interval. Rozpracovaný rozhovor není splnění. Všechna nová potvrzená
check-in ID tohoto profilu jsou v této verzi splněním jediné obecné kontroly.
Nejde ještě o vazbu na konkrétní typ dotazníku či individuální pozvánku.
Po pozvánce se odešle nejvýše jedna stejná připomínka za zadaný odstup;
při další neodpovědi zůstává plán čekat. Opožděný běh neposílá dvě zprávy
najednou. Příjemce se vždy načítá z aktuální pracovní karty.

SQLite transakce serializuje výběr i odeslání; souběžné běžné průchody
neposílají stejný krok znovu. SMTP běží uvnitř transakce, proto používat
jeden plánovací proces; může krátce blokovat příjem zpráv ve webu.
Pád po přijetí SMTP před commitem může vést k opakování e-mailu.
Chyba není úspěch, vrací stav `failed` a exit code 1; další spuštění opakuje
pokus. Nejde o doručovací frontu, evidenci převzetí nebo klinickou eskalaci.
Testy `test_notification_scheduler.py` používají syntetická data, řízený čas
a náhradu SMTP; ověřují i restart, souběh a zachování schématu událostí.
