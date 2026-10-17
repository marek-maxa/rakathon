# Architektura a spuštění

Python 3.12 + uv. Web používá Flask/Jinja, HTML formuláře a Plotly;
JavaScript zobrazuje průběh zpracování a brání opakovanému odeslání.
Manifest a lock jsou v kořeni repozitáře. Triážní jádro nemá vlastní runtime
závislosti. Požadované budoucí chování popisuje [plán](meddi-onco-plan.md).

## Implementovaný stav

| Část | Co existuje | Co chybí pro cílový tok |
| --- | --- | --- |
| `llm_intake/` | Obecná extrakce, katalog 49 otázek, cílené větvení, potvrzení/opravy, omezený MASTER dialog | Výběr priorit podle rizika, bezpečnostní bod před dalším cíleným voláním, trvalé obnovení |
| `meddi/` | Sdílená deterministická pravidla, normalizace, validace, zdrojované důvody a výstupní politika | Úplné vstupy a klinické mapování, obecná nejistota/trendy, karta a orchestrace |
| `web/export.py`, `web/triage.py` | Export vybraných ověřených měření s původem, živé trendy stávajícího adaptéru a zdrojovaný kontext léčby | Úplný registr měření/epizod a skutečného podání léčby |
| `web/app.py` | Vstup Pacient/Lékař, pacientský výběr profilu, MASTER, cílené doptání, společná kontrola, opravy a potvrzení | Přihlášení/oprávnění, volba zastupování, personalizace a bezpečnostní výstup během sběru |
| `web/patient_store.py` | Pracovní kopie pacienta a atomické přidání potvrzeného check-inu | Sjednocení projekce s událostmi, průběžné revize a podpora více procesů |
| `web/event_store.py` | SQLite deník původních zpráv před LLM, stabilní ID, dohledatelné opravy a deduplikace | Trvalé výsledky zpracování a obnova dialogu K2b; úplná historie měření/revizí K2c |
| `web/patient_report.py`, `meddi/status.py` | Poslední/historická triáž, stručná kartička, přehled `/team`, historie odpovědí a měření, nezelené incidenty a grafy | Aktivní epizody, souhrn vývoje, plán kontrol a skutečné předání/převzetí |
| `notifications/` | Samostatný formulář pro pevný testovací e-mail a SMTP transport | Napojení na triáž, adresáti/priorita, spolehlivé předání a převzetí |
| `main.py` | Chronologicky omezené strukturované vstupy a oddělené porovnání s referencemi | Replay celého toku včetně zpráv, kontrol, intervencí a souhrnů |

Plánovač, samostatný formulář měření/přeměření, úplný odborný souhrn vývoje
a skutečné předání monitorovacímu centru nejsou implementované.

## Moduly a datové cesty

| Modul | Rozhraní / odpovědnost |
| --- | --- |
| `llm_intake.master` | `MasterExtractor`, `analyze_message`: zpráva → fakta a kandidáti otázek |
| `llm_intake.core`, `flow`, `dialogue` | Jedna odpověď, větvení a MASTER kontakt; [kontrakt](../llm_intake/MASTER_CONTRACT.md) |
| `meddi.form` | `prepare_checkin`: původní formát → normalizované odpovědi a zdrojové barvy |
| `meddi.patient_inputs` | `build_triage_inputs(patient, checkin)` → prepared/context/observations dostupné k check-inu |
| `meddi.pipeline` | `evaluate_contact(packet, patient_snapshot=None, *, context=None, now=None)` |
| `meddi.triage`, `clinical_rules`, `answer_coverage` | Sdílený výpočet pravidel, pokrytí a nevyřešených vstupů |
| `meddi.disposition` | `resolve_disposition`: výsledná úroveň, krok, kontaktní instrukce a doporučení |
| `meddi.validation` | Domény, typy a jednotky; neplatný vstup není negativní nález |
| Kořenový `triage.py` | Kompatibilní vstupy delegující do `meddi/`; ploché API má omezený rozsah čtyř kritérií |
| `meddi.loader` | Načtení původních pacientů; reference načítat pouze v hodnoticí větvi |
| `web.event_store` | `EventStore(path).accept(owner_id, contact_id, message, *, question_id=None, corrects_event_id=None)` → uložená zdrojová zpráva; `get(owner_id, event_id)` a `contact_messages(owner_id, contact_id)` → čtení deníku |

Živý web:

```text
MessageEvent → EventStore.accept (commit původní zprávy)
             → MasterDialogue.start/submit
             → snapshot llm_intake/v1
             → web.triage.assess_contact
             → meddi.pipeline.evaluate_contact
             → meddi.triage.evaluate_checkin → resolve_disposition
```

Po `confirm_all()` se výpočet zopakuje a export s celým hodnocením uloží.
`MasterDialogue` sám triáž nevolá; jeho vnitřní cílená extrakce může předcházet
návratu do webové vrstvy. Pro orchestraci je to otevřená integrační mezera.

Historický check-in:

```text
build_triage_inputs → evaluate_checkin → resolve_disposition
```

Tato cesta interpretuje strukturované údaje; neextrahuje obsah původní
`zprava_pacienta`. Úplná rovnocennost nových a importovaných zpráv je úkol K7.
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
| `/assets/plotly-<version>.min.js` | Lokálně poskytovaný Plotly skript |
| `/static/<path:filename>` | Styly a skripty webu |

Úvodní volba vede pacienta na `/patient`, lékaře na `/team`. Pacientská
navigace neodkazuje přímo do zdravotnického reportu, lékařský přehled vede
do detailů. Nenápadný odkaz „Změnit rozhraní“ v patičce označené Demo
vrací na úvod bez zrušení rozpracovaného
rozhovoru. Jde o oddělení navigace dema, nikoli kontrolu přístupu;
lékařské URL zůstávají přímo dostupné. Přihlašování není součástí této změny.

Výběr „Ukázkový pacient“ je výslovně označený výběr syntetického profilu
pro demonstraci, nikoli autentizace. V cílovém pacientském vstupu má profil
vycházet z přihlášeného účtu nebo pozvánky; seznam pacientů patří lékaři.
Tento mechanismus je odložený, nevytvářet jej před M2.
Výchozí MASTER zní „Jak se dnes cítíte?“.
Web používá `bulk_confirmation=True`: návrhy se kontrolují společně,
`revise(index)` otevře opravu a zneplatní závislé odpovědi, `confirm_all()`
potvrdí jen vyřešené návrhy. Fakta z obecné extrakce tím nejsou samostatně
potvrzená. Výchozí `MAX_QUESTIONS=6` omezuje počet položených otázek včetně MASTER.

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

Předání je viditelně simulované. Přehled nemá frontu, odesílání, převzetí,
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
`DATA_DIR` mění kořen výstupu; `data/` ignoruje Git. První zápis vytvoří pracovní
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

- Triáž se ve formuláři vykreslí až po potvrzení a úspěšném zápisu, pro všechny
  barvy. Některá upozornění možností se zobrazují při kontrole souhrnu;
  nejsou úplnou bezpečnostní reakcí. Konflikt s okamžitým kritickým krokem
  je v [rozhodnutích](decisions.md#otevřený-konflikt-bezpečnostního-výstupu).
- `MasterDialogue.start/submit` může po obecné extrakci spustit cílené LLM
  dříve, než se řízení vrátí do `assess_contact`. Chyba cíleného volání tak
  může zabránit vyhodnocení již vytěženého rizika. K4 potřebuje bezpečnostní
  bod uvnitř tohoto pořadí, nikoli jen další výpočet po návratu do webu.
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

`main.py` srovnává pouze strukturovanou cestu s referencemi, nikoli celý produkt.
Vyšší výsledek není automaticky zbytečná eskalace a `requires_review` zahrnuje
i chybějící podmínky hypotetických pravidel. Prošlé testy současného skrývání
červené triáže neprokazují splnění P07.
`--comparison` filtruje řádky, souhrn stále počítá celou sadu. Testy intake/webu
používají náhrady LLM; automatické testy SMTP zatím chybí. Živé evaluace jsou
samostatná explicitní volání se syntetickými daty.
Prošlé testy a správné schéma neprokazují klinickou správnost nebo úplnost
extrakce. Testovací výsledky průběžně získávat příkazy, nevést jejich historii
jako součást specifikace.

Testy `tests/test_event_store.py` a `tests/test_web_events.py` ověřují K2a:
čtení v novém Python procesu, souběžné příjmy a opakování, transakční selhání,
příjem před LLM, chybu extrakce, odmítnutí starého/cizího formuláře a opravy.
Používají dočasnou databázi a syntetické zprávy bez sítě. Neověřují obsluhu
živého LLM, klinickou správnost, obnovení dialogu K2b ani provoz ve Windows.
