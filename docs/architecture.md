# Architektura a spuštění

Python 3.12 + uv. Web používá Flask/Jinja, HTML formuláře a Plotly;
JavaScript zobrazuje průběh zpracování a brání opakovanému odeslání.
Manifest a lock jsou v kořeni repozitáře. Triážní jádro nemá vlastní runtime
závislosti. Požadované budoucí chování popisuje [plán](meddi-onco-plan.md).

## Implementovaný stav

| Část | Co existuje | Co chybí pro cílový tok |
| --- | --- | --- |
| `llm_intake/` | Obecná extrakce, katalog 49 otázek, cílený MASTER, společné potvrzení/opravy a volitelný checkpoint před cílenou extrakcí | Výběr priorit podle rizika, trvalé obnovení |
| `meddi/` | Sdílená deterministická pravidla, normalizace, validace, zdrojované důvody a výstupní politika | Úplné vstupy a klinické mapování, obecná nejistota/trendy, karta a orchestrace |
| `web/export.py`, `web/triage.py` | Export vybraných ověřených měření s původem, živé trendy stávajícího adaptéru a zdrojovaný kontext léčby | Úplný registr měření/epizod a skutečného podání léčby |
| `web/app.py` | Společné heslo dema, vstup Pacient/Lékař, výběr profilu, cílený MASTER, kontrola/opravy a naléhavá instrukce během sběru | Individuální oprávnění, volba zastupování, personalizace |
| `web/patient_store.py` | Pracovní kopie pacienta, atomické přidání potvrzeného check-inu a zdrojově vázaná uložená extrakce historické zprávy | Sjednocení projekce s událostmi, průběžné revize a podpora více procesů |
| `web/event_store.py` | SQLite deník původních zpráv před LLM, stabilní ID, dohledatelné opravy a deduplikace | Trvalé výsledky zpracování a obnova dialogu K2b; úplná historie měření/revizí K2c |
| `web/patient_report.py`, `meddi/status.py` | Poslední/historická triáž, stručná kartička, přehled `/team`, historie odpovědí a měření, nezelené incidenty a grafy | Aktivní epizody, souhrn vývoje, plán kontrol a skutečné předání/převzetí |
| `notifications/` | Samostatný formulář pro pevný testovací e-mail a SMTP transport | Napojení na triáž, adresáti/priorita, spolehlivé předání a převzetí |
| `main.py`, `meddi/messages.py` | Strukturovaný replay, volitelná extrakce historických zpráv, konflikty a návrhy doptání, reference oddělené | Úplné klinické pokrytí šesti situací, reakce na odpovědi, intervence a souhrny |

Plánovač, samostatný formulář měření/přeměření, úplný odborný souhrn vývoje
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
pečujícího v kontraktu; jeho volba ve formuláři ještě není implementovaná.
Ukládá se projekce téhož konečného hodnocení v čase `evaluated_at`.
Datum/čas check-inu jsou v Europe/Prague a čas dostupnosti má pásmo.
Adaptér trendů respektuje i explicitní čas měření a jeho dostupnost;
graf používá datum pozorování, pokud je známé. Pro Windows je přidané `tzdata`.
Bez explicitního času pozorování zůstává výchozím čas přijetí zprávy;
relativní historický čas se automaticky neodhaduje.

Tvar původních dat: [README balíčku §5](../rakathon_meddi_onco_data/README.md#5-datový-slovník).
Trend a kontext: [pravidla triáže §4–6](../rakathon_meddi_onco_data/docs/pravidla_triaze.md).

## Web a ukládání

| Cesta | Význam |
| --- | --- |
| `/` | Úvodní volba rozhraní Pacient / Lékař |
| `/patient` | Pacientský výběr profilu a MASTER kontakt, GET i POST |
| `/patients/<patient_id>/report` | Report profilu z pracovní kopie nebo původních dat |
| `/team` | Demonstrační přehled požadavků z posledního hodnocení každého pacienta |
| `/patients/<patient_id>/checkins/<checkin_id>/analyze-message` | Explicitní POST pro extrakci historické zprávy, kontrola session tokenu a zdroje |
| `/assets/plotly-<version>.min.js` | Lokálně poskytovaný Plotly skript |
| `/static/<path:filename>` | Styly a skripty webu |

Úvodní volba vede pacienta na `/patient`, lékaře na `/team`. Pacientská
navigace neodkazuje přímo do zdravotnického reportu, lékařský přehled vede
do detailů. Nenápadný odkaz „Změnit rozhraní“ v patičce označené Demo
vrací na úvod bez zrušení rozpracovaného
rozhovoru. Jde o oddělení navigace dema, nikoli kontrolu přístupu;
všechny cesty nyní chrání společné heslo dema (Basic Auth). Individuální
role a vazba účtu na pacienta implementované nejsou.

Výběr „Ukázkový pacient“ je výslovně označený výběr syntetického profilu
pro demonstraci, nikoli autentizace. V cílovém pacientském vstupu má profil
vycházet z přihlášeného účtu nebo pozvánky; seznam pacientů patří lékaři.
Tento mechanismus je odložený, nevytvářet jej před M2.
Výchozí MASTER zní „Jak se dnes cítíte?“.
Web používá `bulk_confirmation=True`: návrhy se kontrolují společně,
`revise(index)` otevře opravu a zneplatní závislé odpovědi, `confirm_all()`
potvrdí jen vyřešené návrhy. Fakta z obecné extrakce tím nejsou samostatně
potvrzená. Web má `MAX_QUESTIONS=6` a používá cílený režim:
MASTER vybírá konkrétní relevantní otázky, nikoli celé dotazníky. Již sdělené
údaje se využijí přes `Intake.seed`; úplná odpověď jde do společné kontroly,
chybějící rozlišení vyvolá doptání. Zachovají se původní otázky a zdroje,
nejde o domyšlené pacientské odpovědi.

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
vlastní úložiště ani další LLM volání; časové lhůty zatím přebírá z obecného
kontaktního textu backendu. Plné směrování a výpočet termínů zůstávají M4.
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
textu při příjmu neodhaduje. Web zatím zaznamenává autora `patient`;
úložiště přijímá i ostatní role kontraktu, jejich volba v UI je stále K8.

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
- Historie incidentů není registr aktivních klíčových/varovných nálezů.
  Označení „varovné“ v reportu zahrnuje i žluté historické údaje, a proto
  neodpovídá užšímu týmovému významu aktuálních varovných příznaků.
- `upozornit_tym` je požadovaná akce v datech. Neprokazuje odeslání ani převzetí.
  Chybí trvalá evidence příjemce, priority, termínu, pokusů a převzetí;
  samostatné SMTP demo ji nenahrazuje.
- `web.app` předává explicitní čas hodnocení s pásmem; export a adaptér
  timestampovaných měření jej převádějí do `Europe/Prague`. `disposition`
  zatím vrací obecný kontaktní text, nikoli termín vypočtený pro konkrétní
  okamžik. Směrování podle pracovního kalendáře zůstává M4.

## Spuštění a kontroly

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
20 úspěšných formulářů. `notifications.mailer` posílá pevný text bez
klinických údajů. SMTP přijetí není potvrzení doručení ani klinické předání.
Web načítá také `notifications/.env` bez přepsání prostředí.

Pacientský konečný výsledek má výrazný barevný panel, slovní název barvy,
symbol a velké doporučení. Červená má syté výstražné záhlaví. Klinické
texty a výpočet zůstávají společné s backendem.

`tests/test_notifications.py` a `tests/test_patient_mail.py` ověřují SMTP
a formuláře s náhradou transportu; mailové testy používají Basic Auth dema.
