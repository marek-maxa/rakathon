# Technické řešení

Základ: Python 3.12 + uv, Linux / Windows PowerShell. Vývojové nástroje: pytest a Ruff.
Implementované jsou `llm_intake/` a společné výpočetní jádro `meddi/` bez runtime
závislostí. Kořenový `triage.py` zachovává starší vstupní funkce a deleguje do
`meddi/`. Pacientská karta a celá aplikace zatím nejsou implementované.

## Aktuální cílový plán pipeline a webu (17. 10. 2026)

[Zdrojovaná specifikace a kroky K0–K10](meddi-onco-plan.md) jsou aktuálním
plánem po nové revizi všech podkladů MEDDI. Obsahují požadavky P01–P27,
klinický inventář, datové závislosti, otevřené otázky a podmínky dokončení.
V této relaci tým zvolil pouze plán; přenos do `web` následuje po domluvě.
Dosavadní odklad webu a interpretace zpráv byl omezením předchozích etap,
nikoli cílovým omezením tohoto plánu.

Cílová aplikační služba: uložit původní událost → kontext dostupný v čase →
strukturované vstupy / obecná extrakce každé zprávy → `evaluate_contact` →
urgentní instrukce a předání podle potřeby → nálezy, cílené doptání a sledování.
Na konci dotazníku znovu vypočítat a uložit revizi triáže, doporučení a souhrn.
Bezpečnostní bod musí být před dalším cíleným LLM voláním, nikoli až po návratu
`MasterDialogue.start/submit`, které dnes uvnitř pokračují k další extrakci.
Tyto nadřazené komponenty nejsou implementované tímto zápisem.

Rozhraní zachovat: interní `llm_intake/v1` → `meddi_contact_assessment/v1`
podle [backend.md](backend.md); český finální check-in export je samostatný
adaptér podle README pořadatele. Karta ukládá celý kontakt i revize, má stabilní
`patient_id`, otevřené epizody a sledování. Klíčové nálezy zahrnou všechny
nezelené odpovědi/nálezy i relevantní zlepšení a kontext; aktuální varovné
nálezy vedoucí k 3/4 tvoří jejich podmnožinu. Doporučení vychází z nálezů,
úrovně a pravidel i při úrovni 1/2. Poslední skutečná chemoterapie a odstup
se dokládají zdrojem, ne jen existencí cyklu.

Webový snapshot `origin/web=6aeb385` má nekompatibilní potvrzovací API a
ztrátový export. Přesný plán zachování Flasku, formuláře, stylů a JS je
v §8 specifikace. Aktuální main modul `web` nemá; příkaz
`uv run --locked python -m web.app` bude platný až po K1 ve větvi web.
Existující backendový příkaz je níže. Nové úložné/API návrhy ve specifikaci
nejsou dosud volatelné moduly.

Následující aktuální backendový kontrakt zůstává platný. Starší revize a
popisy původních prototypů níže jsou historie vývoje: tvrzení o dvou jádrech,
chybějícím adaptéru, neexistujících testech či neplatné validaci nepřebírat
jako dnešní stav. Klinické výjimky a nejasnosti shrnuje §10 aktuálního plánu.

## Společný backend — stav 17. 10. 2026

`meddi.pipeline.evaluate_contact(packet, patient_snapshot=None, *, context=None,
now=None)` propojuje skutečný LLM paket s širším jádrem pravidel. Převádí potvrzené
možnosti i přesně doložená pozorování; zachovává celý původní kontakt, zdroje,
potvrzení, čas a nevyřešené údaje. Nevytváří další LLM požadavky.

```text
MasterDialogue / build_pipeline_packet
    → meddi.pipeline.evaluate_contact + aktuální snapshot karty
    → časový výběr, validace a zachování současných rozporů
    → prepared / context / observations
    → meddi.triage.evaluate_checkin
    → meddi_contact_assessment / v1: minimum + úplnost + zdroje + celý intake
```

Rozhraní, časový kontrakt karty, mapování, omezení a příklady jsou v
[backend.md](backend.md). Funkci lze volat i během dialogu před potvrzením;
samotný `MasterDialogue` zůstává nezávislý, volání řídí budoucí orchestrátor.
Neúplné zelené minimum se navenek vrací jako `color=null`, známé vyšší minimum
zůstává zachováno. Společná validace odmítá NaN/nekonečno, neplatné domény
a jednotky. Dlouhodobá bolest na hrudi již není chybně vykládána jako její negace.

Offline syntetický průchod na Linuxu i v PowerShellu:

```text
uv run --locked python -m meddi.pipeline meddi/contact.example.json --snapshot meddi/snapshot.example.json --output assessment.json
```

Web ani jeho API se neupravovaly. Historické review níže vysvětluje důvody
změny; popis dvou nezávislých sad pravidel už není aktuálním integračním rozhraním.

## Revize připravenosti před sjednocením (16. 10.)

[Revize main a větve web](pipeline-readiness.md) vyhodnocuje stav na `0420073`
a `origin/web` na `6aeb385`. Lze zahájit integrační CLI prototyp, ale hotové
propojení LLM → širší pravidla → karta zatím neexistuje. Kořenový pipeline
adaptér používá pouze čtyři původní podmínky a web očekává další API dialogu,
které na main není. Revize neměnila běžící aplikační kód ani neslučovala větve.

Doporučený nejbližší krok: po opravě doložených chyb jeden adaptér nad
`meddi.triage.evaluate_checkin`, který převede LLM paket a aktuální kontext
karty na `prepared`, `context`, `observations`. Zachovat zdroj, subjekt,
jednotku, čas, nejistotu, potvrzení a nevyřešené údaje. Karta má ukládat
původní události i odvozený stav; export organizačního dotazníku není celý
záznam kontaktu. Konkrétní návrh, ověření 502 testy, výsledek 171 check-inů
a známé chyby jsou v revizi. Jde o doporučení, nikoli již zavedenou fasádu.

## Historický stav po sloučení s d1b58f4

Existují dvě oddělené cesty triáže:

- `main.py` → `meddi.patient_inputs.build_triage_inputs` →
  `meddi.triage.evaluate_checkin`: strukturovaný check-in, kontext léčby,
  historie dostupná v čase a širší pravidla s důvody a `skipped_rules`.
- CLI jedné otázky → kořenový `triage.evaluate_intake`; nový lokální
  `triage.evaluate_pipeline_packet` přijímá i LLM paket a explicitní kontext.
  Nadále používá původní čtyři kritéria, nikoli celé jádro `meddi/`.

`MasterDialogue` sám triáž nevolá. Předání jeho paketu do kořenového adaptéru
je explicitní krok volajícího. Nové exporty z kořene `llm_intake` se načítají
odloženě, aby zůstalo funkční spouštění `python -m ...`.

Následující auditní oddíly popisují cestu `meddi/`; původní popis malého
prototypu a návrhy LLM mají vlastní rozsah. Obě cesty se liší i při neúplném
vstupu: `meddi/` může vrátit zelenou ze známých skóre a současně požadavek
review, kořenový prototyp při známých pouze zelených skóre a neznámém
kritériu vrací `color=null`. Automatické sjednocení není součástí sloučení.

[Porovnání a důvody rozhodnutí](merge-review.md) uvádí zachované změny,
limity adaptéru a otevřené otázky před klinickým propojením.

## Aktuální stav pravidel a vstupů po auditu

Poslední pokyn týmu: implementovat podmínky barvy ze zdrojových pravidel,
**neinterpretovat zprávy a nevytvářet další klinická pravidla**. Následující
oddíl nahrazuje starší tvrzení níže, že CLI nedodává kontext léčby. Automatické
kontakty, interpretace týmových zásahů a zpracování textu jsou mimo tento krok.
`text_observations.py` a `followup.py` nejsou součástí výsledné implementace.

Tok: `patient_inputs.build_triage_inputs(patient, checkin)` → připravený
dotazník z `form.py`, kontext léčby a číselná pozorování →
`triage.evaluate_checkin(prepared, context, observations)` → `main.py`
porovná výsledek s oddělenou referencí. Samotná pravidla nečtou pacientský
soubor ani ground truth. `form.py` dál pouze připravuje hotový dotazník.

Adaptér používá výhradně názvy z `lecba.leky`, časově platné `leky.lek`,
již nastalé `lecba.cykly[].datum_d1`, komorbidity a předchozí měření/check-iny.
Nečte `nazev_scenare`, popis režimu ani poznámky obsahující budoucí změny.
Laboratoře, zprávy a týmové události neinterpretuje. Lék nově nasazený v den
check-inu bez času dostupnosti nepovažuje automaticky za známý. Bez času
check-inu nepoužije jiné záznamy z téhož dne. Den D1 je interpretován podle
README balíčku §5; datum cyklu v těchto datech považujeme za údaj o podání,
nikoli pouhý budoucí plán. To je třeba ověřit pro případné jiné schéma dat.

Z historie počítá pouze podmínky s konkrétními mezemi ve zdroji: tři zvýšená
měření tlaku, změnu váhy za nejvýše tři dny, úbytek váhy v posledním
kalendářním měsíci, změnu soběstačnosti proti výchozímu ECOG a počet
nevyplněných check-inů za sebou. Nevymýšlí číselný práh pro obecný trend,
psychické skóre, stav „řešený týmem“, hypotenzi ani vysoký věk. Obecný
nepříznivý trend a příznak 2. stupně jsou přijatelné jako explicitní
`unfavorable_trend` / `grade_2_symptom_without_warning_signs` ve vstupu.

### Původ DRUG_CLASSES

`DRUG_CLASSES` je ručně sestavené omezené mapování názvů léčiv na vstupní
příznaky léčby, **není to dodaný číselník ani další sada pravidel triáže**.
Neznámý název nebo nedoložené podání vrací `None`; nepřítomnost rozpoznaného
léku nepovažujeme za důkaz nepřítomnosti léčby. V důkazech kontextu jsou
původní rozpoznané názvy a jejich zdrojová pole. Kvalifikované klinické
ověření mapování a dostupnosti léků v čase zůstává otevřené.

| Přiřazení | Zdroj |
| --- | --- |
| 5-FU / kapecitabin → fluoropyrimidin; irinotekan; sunitinib / bevacizumab → antiangiogenní léčba; trastuzumab → kardiotoxická léčba; cisplatina; warfarin → antikoagulace | `rakathon_meddi_onco_data/docs/pravidla_triaze.md`, §3–5, přímo uvedené názvy a skupiny |
| Doxorubicin → antracyklin a cytotoxická chemoterapie | [EMA Caelyx, How does it work](https://www.ema.europa.eu/en/medicines/human/EPAR/caelyx-pegylated-liposomal); kardiotoxické antracykliny uvádí §4 pravidel |
| Fluorouracil / kapecitabin / oxaliplatina jako chemoterapeutické léky | [EMA Xeloda, Overview a How does it work](https://www.ema.europa.eu/en/medicines/human/EPAR/xeloda) |
| Cyklofosfamid / vinkristin / etoposid jako složky chemoterapie | [NCI Ewing Sarcoma Treatment, Chemotherapy](https://www.cancer.gov/types/bone/hp/ewing-treatment-pdq) |
| Cisplatina / karboplatina jako chemoterapie; irinotekan | [NCI Cisplatin](https://www.cancer.gov/about-cancer/treatment/drugs/cisplatin), [NCI CanMED Carboplatin](https://seer.cancer.gov/oncologytoolbox/canmed/ndconc/69339-0367/), [NCI Irinotecan](https://www.cancer.gov/about-cancer/treatment/drugs/irinotecanhydrochloride); etoposid pokrývá předchozí řádek NCI |
| Nivolumab → anti-PD-1; ipilimumab → anti-CTLA-4 | [EMA Opdivo, How does it work](https://www.ema.europa.eu/en/medicines/human/EPAR/opdivo), [EMA společné hodnocení, Opdivo/Yervoy](https://www.ema.europa.eu/en/documents/withdrawal-report/withdrawal-assessment-report-opdivo-and-yervoy-ws1372_en.pdf), popis mechanismu |
| Atezolizumab → anti-PD-L1 | [EMA hodnocení Opdivo/Yervoy](https://www.ema.europa.eu/en/documents/variation-report/opdivo-h-c-ws-2717-epar-assessment-report-variation_en.pdf), popis schválené léčby HCC |
| Morfin → opioid | [EMA Modified-released oral opioids, Overview](https://www.ema.europa.eu/en/medicines/human/referrals/modified-released-oral-opioids) |
| Inzulin / insulin → inzulinová léčba | Doslovný název třídy ze §3 pravidel; bez odvození inzulinu pouze z diagnózy diabetu |

Tyto zdroje dokládají pouze třídy léčiv, nepřebíráme z nich nové prahy nebo
rozhodovací podmínky. Není to univerzální katalog léčiv ani odhad léčby z ID.
Odkazovaný souhrn RMP Imfinzi se při kontrole nepodařilo otevřít; pro tyto
závěry proto používáme výše uvedené dostupné primární zdroje NCI.

### Pokrytí podmínek barvy

Všechny následující podmínky přijímají explicitní strukturovaná pozorování;
existence pravidla neznamená, že jsou potřebné údaje přítomné v dotazníku.
Zdroj všech řádků: `rakathon_meddi_onco_data/docs/pravidla_triaze.md`, uvedený
oddíl. Důvody zachovávají zdroj a skutečné vstupní důkazy.

| Oddíl / skupina | Implementace |
| --- | --- |
| §3 červená: horečka / zimnice při chemoterapii | `fever`, `reported_fever`, `chemotherapy_chills` |
| §3 červená: dýchání / hrudník | klidová dušnost, SpO2 <90, náhlá dušnost + hrudník/palpitace, nová bolest na hrudi |
| §3 červená: neurologie / krvácení | jednotlivé neurologické příznaky; konkrétní místa krvácení, nos >20 minut, úraz hlavy + antikoagulace |
| §3 červená: průjem / zvracení / oběh / břicho | ≥7 nad normál nebo krev; >5 epizod nebo neudržení tekutin + dehydratace; anurie >10 h, mdloba, systolický tlak <90; zástava plynů i stolice + zvracení/kolika |
| §3 červená: tlak / metabolismus / opioidy / psychika | prahy 180/110, vysoký tlak + varovné příznaky; metabolická kombinace; opioidové varovné příznaky; suicidalita + plán/úmysl/prostředky |
| §3 oranžová: pocit / dýchání | pocit 5; SpO2 <92, pokles ≥3 body, ortopnoe |
| §3 oranžová: průjem | 4–6 při rizikové léčbě; neúčinný loperamid **při potvrzeném dodržení schématu**; průjem + břicho na imunoterapii |
| §3 oranžová: příjem / zvracení / tlak / krvácení | všechny uvedené kombinace příjmu, bolesti, močení a závratí; zvracení 3–5 + neudržení tekutin; antiangiogenní tlak 160/100; krvácení/modřiny na antikoagulaci |
| §3 oranžová: další skupiny | jednostranný otok + bolest lýtka; bolest NRS ≥7 po SOS; ranní bolest hlavy + zvracení při mozkovém nádoru; metabolické příznaky při imunoterapii; glykémie <4 při inzulinu; suicidalita nebo beznaděj; zhoršení přes plánované vyšetření |
| §4: příznak 2. stupně | obecná potvrzená podmínka; nevolnost s omezením příjmu, zácpa ≥3 dny, afty omezující jídlo, paronychie a ruka-noha |
| §4: průjem / zvracení / tlak / glykémie | ≤3 nad normál na imunoterapii; zvracení 3–5 při pití; ≥3 zvýšená měření nebo ortostatická hypotenze; glykémie >15 + žízeň + polyurie |
| §4: neuropatie / tinnitus / otoky / funkční stav | přetrvávání mezi cykly nebo jemná motorika; nový tinnitus + cisplatina; otoky 2. stupně nebo >2 kg / 3 dny při kardiotoxické léčbě; ≥5 % / měsíc nebo soběstačnost horší o ≥2 stupně nebo postupný pokles příjmu |
| §4: bolest / psychika / pečující / adherence / výpadek | NRS 4–6 nebo SOS ≥3; potvrzený střední smutek/úzkost; vyčerpání pečujícího; vynechávání léků; ≥3 nevyplněné záznamy |
| §5 a §6.1: kontext a trend | nové uvedené příznaky při imunoterapii, irinotekan a potvrzený interval <12 h bez průjmu nebo právě probíhající průjem; explicitní nepříznivý trend |

U vysokého tlaku s varovnými příznaky už nevytváříme dříve domyšlenou hranici
140/90: požadujeme explicitní `high_blood_pressure`. Párové prahy 180/110,
160/100 a 140/90 nadále používají obvyklé překročení kterékoliv složky; tento
výklad zkratky musí potvrdit mentor. Screeningové škály a ESAS nemají ve
zdroji převod na „střední psychickou zátěž“; numerický práh nepřidáváme.
Neuropatie s obecným omezením ADL neprokazuje specificky jemnou motoriku.
Volba průjmu za posledních 24 hodin neprokazuje interval <12 hodin od poslední
epizody; toto byla opravená záměna při auditu.

Chybějící údaje se podle dřívějšího výslovného pokynu týmu přeskakují a zůstávají
v `skipped_rules`; tato vývojová výjimka ze §6.4 stále platí. Texty se uchovávají
k review, neodvozují pozorování ani barvu. Aktuální údaje se nekombinují se
starými urgentními příznaky způsobem, který by trvale nesl starou červenou.
Stav „řešený týmem a zlepšující se“ zatím není strukturovaný vstup pro snížení
typické žluté (§6.3); barevné přepisy podle textu reference se neprovádějí.

Přehrání a audit:

```text
uv run python main.py
uv run python main.py --comparison lower --details
uv run python main.py --comparison higher --details
uv run pytest -q
uv run ruff check .
```

`--comparison` filtruje řádky, souhrn stále počítá všechny záznamy. Přesný
rozpis zbývajících neshod a skutečně provedené kontroly jsou v `docs/tasks.md`.

## Příprava celého check-inu pro triáž

`meddi.form.prepare_checkin(checkin)` přijímá hotový check-in ve formátu
datového balíčku (`dotazniky`, `odpovedi`, `odpoved_index`, `odpoved`).
Vrací samostatný slovník připravený k JSON serializaci. Data uchovává v paměti;
nezapisuje soubor a neprovádí interaktivní dotazování.

```python
from meddi.form import prepare_checkin
from meddi.loader import load_patient

patient = load_patient("ONC-001")
prepared = prepare_checkin(patient["checkiny"][0])
answers = prepared["answers"]
non_green_answers = prepared["non_green_answers"]
```

`answers` je seznam všech dodaných odpovědí v původním pořadí, včetně zelených,
neobarvených, číselných a textových. Každá položka obsahuje:

- `questionnaire_id`, `questionnaire_instance_id`, `questionnaire_name`
  a `questionnaire_note` pro identifikaci zdroje a význam škál;
- `question_id`, `question`, `type`, `condition`, `instructions` a `note`
  podle definic;
- `value` a `option_indices` jako zachovanou původní odpověď a výběr;
- `selected_options`: zvolené možnosti s `index`, `text`, `color` a `warning`;
- `color`: nejvyšší známou barvu zvolených možností, případně barvu škály ESAS.

Barvy jsou anglické řetězce `green`, `yellow`, `orange`, `red` nebo `null`.
`non_green_answers` obsahuje celé záznamy odpovědí s barvou yellow/orange/red,
aby později bylo možné zobrazit konkrétní otázku, odpověď a upozornění.
`null` znamená chybějící výběr nebo absenci barevného klíče, nikoli zelenou.
Například kladná odpověď na otázku `sebevrazda` nemá v definicích barvu,
ale zůstává v `answers` a zpracovává ji samostatné pravidlo triáže.

Barvy a upozornění se načítají z
`rakathon_meddi_onco_data/docs/dotazniky_definice.json`, nikoli z uložených
barev vstupního check-inu. ESAS používá zjednodušení uvedené v `poznamka`
definice: 1–3 green, 4–5 yellow, 6–10 red. Podmínky otázek se zachovávají,
ale v tomto kroku se nepřepočítávají ani nedoplňují nezodpovězené otázky.

Výstup dále obsahuje `patient_id`, `checkin_id`, `date`, `time`,
`monitoring_day`, `cycle`, `cycle_day`, `status`, `filled_by`, `vital_signs`,
`patient_message` a `attachments`. Měření v `vital_signs` zachovávají původní
názvy polí, hodnoty a zdroje z `vitalni_funkce`. Nedodané údaje zůstávají
`null`; nic se neodhaduje z volného textu, teplotního rozmezí nebo počtu SOS dávek.
Výstupní seznamy a slovníky nesdílejí měnitelná data se vstupem ani definicemi.

Příprava neurčuje finální barvu ani důvod eskalace. Navazující funkce
`meddi.triage.evaluate_checkin` zpracovává její výstup podle následujícího oddílu.
Zdroj: pravidla triáže, §3 (minimální úroveň) a §6.6 (vysvětlitelnost);
README balíčku, §4 / Dotazníky (barvy odpovědí jsou vstupem).

`meddi.form.evaluate_checkin(checkin)` zůstává jako pomocné porovnání nejvyšší
dotazníkové barvy. Používá tentýž připravený výstup; nejde o finální triáž.
`main.py` již porovnává skutečný výstup `meddi.triage.evaluate_checkin`.
Kořenový `triage.py` pro LLM intake je nadále samostatný.

Ověření přípravy: `uv run --locked python -m pytest tests/test_form.py -q`.

## Připravený check-in → triáž s důvody

`meddi.triage.evaluate_checkin(prepared, context=None, observations=None)` přijímá výstup
`prepare_checkin`. Kód vybere nejvyšší úroveň ze spuštěných pravidel, nikoli
maximum barev odpovědí. Formulář se nemění a nevolá triáž při přípravě dat.

```python
from meddi.form import prepare_checkin
from meddi.triage import evaluate_checkin

prepared = prepare_checkin(checkin)
result = evaluate_checkin(prepared, context={
    "chemotherapy_within_6_weeks": True,
})
print(result["color"])
print(result["reasons"])
print(result["non_green_answers"])
```

Základní `context` přijímá explicitně známé boolean/null údaje
`chemotherapy_within_6_weeks`, `pain_persists_after_rescue_dose` a
`suicide_plan_intent_or_means`. Poslední údaj znamená přítomnost plánu, úmyslu
nebo prostředků u kladné odpovědi na otázku o sebevraždě. Aplikace je musí
dodat jen podle informací dostupných v okamžiku check-inu. Tato funkce
neodvozuje léčbu z názvu režimu, nenačítá celý pacientský soubor, historii,
reference ani budoucí události. Počet SOS dávek neurčuje účinek SOS dávky.

README datového balíčku, §5 / Záznam, definuje `den_cyklu`: den 1 = aplikace.
U známého příslušného režimu tedy `den_cyklu - 1` udává dny od začátku cyklu.
`ONC-001-C07` má cyklus 1 a den 10, tedy 9 dní od začátku cyklu
(`pacienti/ONC-001.json`, `lecba.cykly` a příslušný check-in).
Samotný cyklus ale neurčuje chemoterapii: `ONC-004.json`, `lecba.rezim`,
obsahuje cyklickou imunoterapii; `ONC-007.json` a `ONC-009.json` cílenou léčbu.
Pouhé nenulové `cycle`/`cycle_day` se proto nepřevádí na kontext chemoterapie.
Pravidlo horečky používá období během chemoterapie nebo do 6 týdnů po ní
(pravidla, §3 / Horečka), nikoli jen nadir D7–14 (§5). Automatické rozpoznání
typu léčby a ověření skutečné aplikace zůstávají dalším krokem.

Implementovaný rozsah podle `pravidla_triaze.md`, §3–4:

| Vstup | Pravidlo / úroveň |
| --- | --- |
| `vital_signs.teplota_c.hodnota` nebo zvolený teplotní rozsah `teplota` | ≥38 °C v kontextu chemoterapie: red |
| `vital_signs.spo2_pct.hodnota` | <90 % red, jinak <92 % orange |
| `nezadouci_ucinky/pocit`, index 4 | Pocit 5: orange |
| `bolest_analgeticka_terapie/nrs` | 4–6 yellow; ≥7 s přetrváváním po SOS dávce orange |
| `bolest_analgeticka_terapie/sos` | ≥3 dávky denně: yellow (§4) |
| `nezadouci_ucinky/dusnost`, index 3 | Dušnost v klidu: red |
| `nezadouci_ucinky/bol_hrud`, index 1 | Nová bolest na hrudi: red |
| `nezadouci_ucinky/zvraceni`, index 2 | >5 epizod za 24 h: red; nově v clinical_rules.py |
| `nezadouci_ucinky/prujem`, index 2 | Odpověď „více než 7 nad normál“: red |
| `psychoonkologicky_screening/sebevrazda`, index 0 | Nejméně orange; s plánem, úmyslem či prostředky red |

Výstup obsahuje `patient_id`, `checkin_id`, `color`, `scores`, `reasons`,
`non_green_answers`, `skipped_rules`, `requires_review`, `review_issues` a
`scope="supported_structured_checkin_rules"`.
Každý důvod obsahuje `rule_id`, `color`, český `message`, `source` se souborem
a oddílem, `evidence` s úplnými zdrojovými odpověďmi/měřeními/kontextem,
`provisional` a případný `uncertainty_source` (zachované atributy rozhraní;
současná politika už neznámé podmínky prozatímně neeskaluje). Důvody zahrnují všechny
spuštěné eskalace, tedy i nižší než výslednou barvu. Nejde o porovnání
s předchozím check-inem. Nezelené odpovědi zachovávají své původní barvy
a nemusejí odpovídat výsledné úrovni; ESAS se automaticky nepřevádí na NRS.

Na výslovný pokyn týmu používáme dočasnou vývojovou politiku: podmínka
s chybějícím vstupem se přeskočí při určení barvy. `skipped_rules` uchovává
`rule_id`, seznam `missing_fields` a dostupné `evidence`. Chybějící vstup se
nenahradí nulou, false ani zeleným skóre; příslušné skóre zůstane `null`.
Například horečka s neznámou chemoterapií neaktivuje červenou a silná bolest
s neznámým účinkem SOS dávky neaktivuje oranžovou. Kladná odpověď na otázku
o sebevraždě sama potvrzuje oranžovou; bez podrobností se přeskočí pouze
červené pravidlo plánu, úmyslu či prostředků.

Barva je maximum vyhodnotitelných pravidel a může být green i při
`requires_review=true`. Pouze pokud se nedá vyhodnotit vůbec žádné pravidlo,
zůstává `color=null`. Nepodporované odpovědi/měření, zprávy, přílohy a nevyplněné
check-iny se dál zachovávají v `review_issues` a samy nepřebarvují známý výsledek.
Rozpor mezi teplotním rozsahem a měřením nadále zachovává nejvyšší prokázanou
úroveň a přidá `conflicting_temperature`.

Tato politika na pokyn týmu nahrazuje předchozí prozatímní vyšší úrovně;
nenaplňuje automaticky požadavek organizátora na eskalaci při nejistotě
(§6.4). Green nyní znamená jen absenci eskalace ve skutečně vyhodnocených
pravidlech, nikoli dokončené posouzení pacienta. Ani zachování zprávy v review
nenahrazuje zpracování jejího obsahu a přednosti podle §6.2.

Další skupiny tlaku, krvácení, dehydratace, neurologie, metabolismu a opioidů
implementuje `meddi/clinical_rules.py`, viz následující oddíl. Stále nepokrýváme
celý protokol (např. zimnici, pokles saturace proti obvyklému stavu, všechna
pravidla průjmu a časové trendy), kontakty a doporučené kroky. Definice otázky `prujem`
říká „více než 7“, zatímco tvrdé pravidlo začíná na ≥7. Vybraná možnost
podmínku splňuje; přesně 7 stolic vyžaduje samostatně zachycený údaj v dalším
kroku. Obecná odpověď „hospitalizace“ u zvracení/průjmu sama nedokládá
konkrétní počet epizod a je předána k review. Klinický výklad i politika
prozatímních úrovní nadále vyžadují kvalifikované lidské ověření.

CLI zachovává plochý vstup a přidává volitelný režim připraveného check-inu:

```text
uv run --locked python -m meddi.triage prepared.json --checkin
uv run --locked python -m meddi.triage prepared.json --checkin --context context.json
uv run --locked python -m pytest tests/test_checkin_triage.py -q
```

Také ploché `meddi.triage.evaluate_triage(data)` přeskakuje chybějící vstupy
a vrací `skipped_rules`; známá zelená není blokovaná neznámými kritérii.
Kořenový `triage.py`, používaný LLM intake, se v této úpravě nemění.

## Nevolnost a další skupiny klinických pravidel

`meddi/clinical_rules.py` doplňuje požadované skupiny podle pravidel §3–4.
`meddi.triage.evaluate_checkin` jej volá automaticky a sloučí skóre, důvody,
přeskočené podmínky i rozpory s dosavadními pravidly. Plochý prototyp
`evaluate_triage(data)` a kořenový modul pro LLM intake tento nový modul nevolají.

| Skupina | Implementované podmínky |
| --- | --- |
| Příjem jídla (§4) | Nevolnost se sníženým příjmem a afty omezující jídlo: nejméně yellow |
| Tlak (§3–4) | 180/110 red; zvýšený tlak s varovným příznakem red; 160/100 při antiangiogenní léčbě orange; ≥3 zvýšená měření yellow; hypotenze se závratí při vstávání yellow |
| Krvácení (§3) | Krev ve stolici/zvratcích/moči či černá stolice red; nos >20 minut red; úraz hlavy na antikoagulaci red; krvácení nebo nové modřiny při antikoagulaci orange |
| Dehydratace a oběh (§3–4) | Nemočení >10 hodin, mdloba nebo systolický tlak <90 red; neudrží tekutiny a známky dehydratace red; neudrží tekutiny orange; nově tekutá strava s nekontrolovanou bolestí orange; snížený příjem s málo močí/závratí orange |
| Zvracení a břicho (§3–4) | >5 epizod red; 3–5 a neudrží tekutiny orange; 3–5 a pije yellow; zástava plynů i stolice se zvracením nebo kolikou red |
| Neurologie (§3) | Zmatenost, porucha vědomí/probuditelnosti, nereagování, záchvat, nová slabost končetin či porucha řeči red; ranní bolest hlavy se zvracením u mozkového nádoru orange |
| Metabolismus (§3–4) | Zvracení + bolest břicha + zrychlené dýchání při diabetu/imunoterapii red; žízeň + časté močení + hubnutí při imunoterapii orange; glykémie <4 při inzulinu orange; >15 se žízní a častým močením yellow |
| Opioidy (§3) | Nová nápadná spavost, nereagování nebo zpomalené dýchání při opioidech red |

Pro párové prahy tlaku používáme konzervativně překročení kterékoliv složky
(systolický ≥180 **nebo** diastolický ≥110; obdobně 160/100). „Zvýšený tlak“
pro kombinaci s varovnými příznaky operacionalizujeme jako systolický ≥140
nebo diastolický ≥90 podle hranice z §4. Zadání výslovně neříká AND/OR ani
práh pro tuto kombinaci; oba výklady je nutné ověřit s mentorem. Nové příznaky
se neoznačují diagnózou a pravidla nemění léky ani dávky.

Přímé mapování vstupů:

- `vital_signs.tk_sys.hodnota`, `tk_dia.hodnota`, `glykemie_mmol_l.hodnota`
  dodají tlak a glykémii se zachováním zdroje měření.
- `nezadouci_ucinky/nevolnost`, index ≥1, prokazuje snížený příjem; index 0
  ho neprokazuje. Výsledkem je žluté minimum, nikoli automatické vyloučení
  závažnějšího stavu. `ONC-001-C02` je ověřený regresní případ bez reference
  ve vstupu. `nechutenstvi` index ≥1 dodává snížený příjem pro kombinovaná
  pravidla; samo se nezaměňuje za nevolnost.
- `afty` index ≥1 prokazuje omezení jídla. Odpověď „pouze tekutá strava“
  sama nedokládá, že jde o novou změnu; `new_only_liquid_food` se nedoplňuje.
- `krvaceni` index 1 dodává společný signál krvácení/modřin. Nedokládá konkrétní
  místo krvácení. Ani „ano“ u `moceni` nedokládá krev v moči.
- `zvraceni` zachovává rozsahy jako podmínky (1–2, 3–5, >5); nevymýšlí přesné
  číslo. Odpověď pouze o obavě z hospitalizace neprokazuje konkrétní počet.
- `bol_bricho` dokládá bolest břicha a `bol_hrud` bolest na hrudi pro kombinace;
  samy neurčují další dosud neznámé příznaky.

Dodatečný `context` podporuje boolean/null: `anticoagulation`,
`antiangiogenic_treatment`, `diabetes`, `immunotherapy`, `insulin_treatment`,
`brain_tumor`, `opioid_treatment`. Tyto skutečnosti dodává aplikace podle
údajů dostupných k danému okamžiku; z názvů léčiv či režimů se zde neodhadují.

`observations` přijímá explicitní pozorování, nikoli volnou zprávu:

```python
result = evaluate_checkin(prepared,
    context={"opioid_treatment": True},
    observations={
        "slow_breathing": {
            "value": True,
            "source": {"field": "patient_message", "quote": "Syntetické potvrzené sdělení"},
        },
    },
)
```

Hodnota může být přímo boolean/číslo nebo záznam `{"value": ..., "source": ...}`.
`source` je volitelné a celé se zachová v důkazu. Číselná pozorování jsou konečná
a nezáporná; boolean není číslo. Přijímaná pole:

| Typ/skupina | Pole observations |
| --- | --- |
| Čísla | `systolic_bp`, `diastolic_bp`, `glucose_mmol_l`, `nosebleed_minutes`, `hours_without_urine`, `vomiting_episodes_24h`, `elevated_bp_measurements` |
| Příjem / tekutiny | `nausea_reduced_intake`, `mouth_sores_limit_eating`, `reduced_intake`, `cannot_keep_fluids`, `dehydration_signs`, `new_only_liquid_food`, `pain_uncontrolled`, `low_urine`, `orthostatic_dizziness`, `drinking_maintained`, `fainting` |
| Tlak a varovné příznaky | `hypotension`, `severe_headache`, `vision_disturbance`, `speech_disturbance`, `chest_pain` |
| Krvácení | `blood_in_stool`, `blood_in_vomit`, `black_stool`, `blood_in_urine`, `head_injury`, `bleeding_or_new_bruises`, `bleeding`, `new_bruises` |
| Neurologie | `confusion`, `consciousness_disturbance`, `difficulty_waking`, `seizure`, `new_limb_weakness`, `speech_disturbance`, `unresponsiveness`, `morning_headache` |
| Metabolismus / břicho | `vomiting`, `abdominal_pain`, `rapid_breathing`, `polydipsia`, `frequent_urination`, `weight_loss`, `no_gas`, `no_stool`, `colicky_abdominal_pain` |
| Opioidy | `new_marked_drowsiness`, `unresponsiveness`, `slow_breathing` |

`elevated_bp_measurements` znamená počet skutečně známých měření alespoň
140 systolicky nebo 90 diastolicky; nesmí zahrnovat budoucí měření. Zde se
historie nesčítá ani nenačítá. Z dechové frekvence se bez zadané klinické
definice neodvozuje `slow_breathing` ani `rapid_breathing`. Diagnózy a nové
příznaky, které existují jen ve zprávě, vyžadují navazující extrakci/potvrzení.

Složené podmínky rozlišují true/false/unknown: u AND známé false vyloučí
pravidlo bez dalších údajů, u OR známé true stačí ke spuštění. Jinak se
zaznamenají přesně chybějící pole do skipped_rules. Rozporné hodnoty se
zachovají v review_issues a použije se nejvyšší prokázaná úroveň; není přepsán
původní formulář ani pozorování. Volný text se automaticky neparsuje a
reference zůstávají oddělené od rozhodování.

```text
uv run --locked python -m meddi.triage prepared.json --checkin --context context.json --observations observations.json
uv run --locked python -m pytest tests/test_clinical_rules.py -q
```

## Porovnání ground truth a pravidel po check-inech

`main.py` spouští `prepare_checkin` → `meddi.triage.evaluate_checkin`
pro každý check-in. Reference páruje přes `checkin_id` až pro porovnání;
do triáže předává pouze připravený aktuální check-in, bez reference,
názvu scénáře, budoucích záznamů nebo celého pacientského souboru.
Duplicitní ID a chybějící či přebývající reference odmítá.

```text
uv run --locked python main.py
uv run --locked python main.py ONC-001
uv run --locked python main.py ONC-001 --details
```

Výchozí tabulka obsahuje CHECK-IN, GROUND TRUTH, RULES, COMPARISON a REVIEW.
Barvy jsou anglicky; `undetermined` znamená neurčený výsledek, nikoli zelenou
ani automaticky nižší úroveň. COMPARISON je match/lower/higher/undetermined
vůči referenci. Hvězdička u RULES označuje prozatímní výslednou úroveň;
potvrzená červená není označena hvězdičkou jen kvůli nižšímu prozatímnímu
oranžovému pravidlu. Souhrn ukazuje shody vůči všem záznamům, počet neurčených
výsledků a počet záznamů k review. `--details` přidá zdůvodnění reference,
důvody pravidel s odkazy na zdroj, kódy položek k review a přeskočená pravidla
s konkrétními chybějícími vstupy.
CLI nastavuje výstup na UTF-8, aby i v PowerShellu prošla zdůvodnění
s českou diakritikou a symboly jako ≥.

`compare_patient` vrací po check-inech `rules_color`, `reference_color`,
`reference_reason`, `comparison`, `requires_review`, `provisional`,
`reasons`, `review_issues` a `skipped_rules`. Nahrazuje předchozí dotazníkový baseline
(`questionnaire_color`); dřívější shoda 117/171 se vztahovala k tomuto baseline.

CLI zatím nedodává kontext léčby. Jde o průběžné vývojové porovnání omezené
sady pravidel, nikoli o úplné vyhodnocení klinické správnosti. Neurčené
výsledky zůstávají jen tam, kde není žádné vyhodnotitelné pravidlo. Chybějící
SpO2 či NRS se zaznamenají do skipped_rules a neblokují jinou známou barvu;
nevyhodnocené odpovědi a zprávy zůstávají k review. Chybějící měření samo
není totéž jako pravidlo o nevyplněných check-inech (§4 pravidel).

## Minimální propojení intake → triáž

```text
uv run python -m llm_intake --question pocit
uv run python -m llm_intake --questionnaire bolest_analgeticka_terapie --question nrs
```

Po pacientově potvrzení CLI zavolá `triage.evaluate_intake(result)` a vypíše
barvu a upozornění na neúplné posouzení. `pocit` mapuje potvrzený index 0–4
na `overall_feeling` 1–5; `nrs` předává číselnou odpověď do `pain_nrs`.
`triage.evaluate_pipeline_packet(packet, context=None)` i `evaluate_intake`
přijímají také celý pipeline paket z `build_pipeline_packet` nebo `MasterDialogue.snapshot()`:
mapují potvrzené odpovědi i naměřená fakta pacienta (např. teplota) a umožňují
předat kontext léčby (např. probíhající chemoterapii) z pacientské karty.
Jiné otázky ani nepotvrzené návrhy nepřevádí na klinická fakta. Barvy možností
dotazníku se k určení výsledné triáže nepoužívají.

Příkaz stále řeší jednu otázku. Pocit 5 tak vrátí `orange`, bolest 4–6 `yellow`;
ostatní potřebné údaje zůstávají neznámé a `requires_review` je true.
Bez prokázané eskalace vypíše „neurčeno“, nikoli zelenou. Výchozí otázka
`unava` zatím nemá mapování.

## Návrh: MASTER QUESTION a karta v čase

[master-question.md](master-question.md) propojuje otevřenou otázku se
`zprava_pacienta`, extrakcí faktů, výběrem témat, stávajícím intake a budoucími
kontrolami z karty. Omezená orchestrace LLM dialogu už existuje níže;
konzervativní vyhodnocení alternativ a napojení na kartu jsou zatím návrh.

Zásadní hranice: každá zpráva nejprve poskytne fakta pro nezávislou kontrolu
tvrdých pravidel; běžné doptávání ani potvrzení nesmějí blokovat již známé
urgentní předání. Nejistota má zůstat v datech; vyšší prozatímní úroveň vypočte
kód z podložených možných interpretací, nezapisuje se jako vymyšlená potvrzená
odpověď. Barvy možností nejsou úrovně triáže.

Současná triáž pokrývá jen část pravidel a intake při `unclear` nevrací
alternativy, takže celý tento bezpečnostní požadavek ještě neplní. První
samostatný LLM kontrakt je uveden níže; pokrytí pravidel a jejich adaptér
zůstávají úkolem budoucí integrace. Aktuálních 49 otázek nevyžaduje vektorovou databázi;
plánujeme explicitní katalog a výběr podle faktů, chybějících údajů a splatných
kontrol. Vedle limitu doptání jedné otázky potřebujeme i rozpočet celého kontaktu.

## Implementováno: LLM kontrakt MASTER QUESTION

[Popis rozhraní a příklad](../llm_intake/MASTER_CONTRACT.md):
`llm_intake.master_contract` definuje `MessageEvent`, `Fact`, `NumericRange`
a `build_packet(message, facts) -> dict`. Samostatný paket verze 1 obsahuje
původní zprávu a nepotvrzené fakty s citací, subjektem, nejistotou a časovým textem.
Neobsahuje triáž a nenahrazuje export intake v2. Čas dostupnosti a zdroj dodává
aplikace; relativní čas ani interval se nepřevádějí na domyšlené přesné měření.

`llm_intake.question_catalog.load_catalog()` čte všech 49 dvojic ID ze zdrojových
definic. `load_topic_catalog()` je spojí s `question_topics.json`: klíčová slova,
anglické aliasy a kontext pro každou otázku. Kontroluje přesnou shodu 49/49;
zdrojové otázky ani jejich možnosti nekopíruje. `resolve_topics(topic_ids)`
vrací balíčky z přesných ID; `lookup_questions(concepts)` zůstává kompatibilní
alternativou pro vlastní extraktory bez ID. Zachovává podmínky větvení,
ale nevyhodnocuje je. Jde o kandidátní vazby,
ne plánovač: i popření nebo potíž pečujícího má vazbu, kterou musí následný
výběr posoudit podle celého faktu a kontextu.

Pět syntetických příkladů v `llm_intake/master_examples.json` vymezuje požadovaný
převod a používá je nový extraktor níže. Omezený dialog už potvrzuje vybrané
odpovědi; samostatná fakta zůstávají návrhy. Karta, časování a triáž se zde neimplementují.

## Implementováno: extrakce MASTER QUESTION a kandidáti otázek

`llm_intake.master.MasterExtractor(client)(message)` vrací validovaný seznam
`Fact`. Vlastní `master_prompt.md` a `master_schema.json`, pět příkladů v kontextu
a celý katalog všech 49 otázek včetně klíčových slov a možností odpovědí.
Fakt obsahuje `topic_ids`, která striktní schéma omezuje enumem z katalogu;
kód validuje a mechanicky mapuje ID, bez top-k nebo embeddingů.
Pro model posílá text, typ, návod, poznámku a přesné možnosti; technická
metadata pořadí/podmínek zůstávají v aplikaci a exportu. Poznámka formuláře
je jednou v `questionnaire_context`. Katalog a příklady tvoří statický prefix
před proměnlivou zprávou. JSON pro API je kompaktní.
Model nedostává identifikátory
pacienta ani systémový čas; časová vyjádření zachovává doslovně. Další pojmy
uchová i bez odpovídající otázky. HTTP transport a autentizaci sdílí s intake
přes `Client.structured_payload()` a `Client.send()`.

`analyze_message(message, extract)` vrací pipeline paket s původní zprávou,
nepotvrzenými fakty a prázdným `question_answers`. Přidává `analysis_status`
(extracted/no_facts), `question_candidates` (balíček otázky + indexy důvodových
faktů), `unmapped_concepts` a `unknown_subject_fact_indices`. Popření a potíže
pečujícího nevyvolávají otázku na pacienta; fakta s neurčeným subjektem jsou
viditelná mimo automatický výběr. Kandidáti se neduplikují a respektují pořadí
definic, nikoli pořadí zmínek ve zprávě. Nejde o triáž ani hotový plán.

CLI pro zaznamenanou syntetickou odpověď, shodné pro Linux i PowerShell:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.master llm_intake/master_input.example.json
```

Na stdout je JSON, při chybě zpráva na stderr a kód 1. Nevalidní či nedokončený
výstup se nepřekládá na úspěšný prázdný výsledek. Samotné `no_facts` neznamená
dobrý stav pacienta. [Rozhraní a živý syntetický výstup](../llm_intake/MASTER_CONTRACT.md).
Kandidáty a již sdělené hodnoty propojuje `MasterDialogue` níže. Samotná funkce
`analyze_message` neposuzuje naléhavost, stáří nebo celkový rozpočet.

## Implementováno: omezený interaktivní MASTER dialog

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.dialogue --debug --output .scratch/master-output.json
```

`llm_intake.dialogue.MasterDialogue` spojuje extrakci zprávy, kandidáty,
`QuestionnaireFlow` a `Intake`. `start(MessageEvent)` zahájí kontakt;
`active` je aktuální cílená relace. Dále `submit(MessageEvent)`, `confirm()`,
`reject()`, `cancel()` a `snapshot()`. Předávaná odpověď musí mít nové ID,
správného pacienta, skutečnou otázku a čas ne starší než poslední zpráva.
Fakta všech slovních odpovědí se uchovávají a nová témata vstoupí do flow
po uzavření aktivní relace; už ukončené otázky se neopakují.

`Intake.seed(messages)` využije existující zprávy bez změny jejich původních
otázek. `submit_event(message)` připojí další odpověď se zdrojem. Úplný údaj
jde přímo k potvrzení, neúplný k doptání. `Client.extract_events` předává
modelu navíc autory zdrojů. Původní `submit(text)` a tříargumentový extraktor
zůstávají funkční. Export v2 přidá `source_events` jen při použití událostí;
pipeline `turns` pak doplní ID, čas dostupnosti a autora zdroje.

Kontakt má výchozí `max_questions=6` včetně MASTER, potvrzení a oprav;
`max_clarifications=2` dál omezuje jednotlivý parametr. Vyčerpání kontaktu je
`limited`, nedokončená větev či nepokrytý pojem `unresolved`, přerušení
`cancelled`, úspěšný sběr `complete` (nikoli klinické vyhodnocení). JSON
zahrnuje všechny zpracované `messages`, `facts` se správnými zdroji,
`question_answers` a `dialogue` se stavem, limitem a průběhem větví.
`dialogue.pending_topic_ids` zpřístupňuje připravené i blokované otázky,
které zbývají po vyčerpání rozpočtu; fakta a kandidáti se tím nezkracují.

CLI podporuje `/moznosti`, `/konec`, `--input`, `--debug`, `--output`,
`--max-questions`, `--max-clarifications` a simulovaný `--at`.
Bez vstupního souboru se ptá od MASTER; se souborem pokračuje z uložené
zprávy. Čas kontaktu se automaticky neposouvá. Chyba nezpůsobí potvrzení
ani prázdný úspěch; CLI skončí 1, může uložit dosud zpracovaný stav a nemá
automatické obnovení. Kódy 0/2 značí dokončený/neúplný nebo přerušený sběr.
Vyčerpaný rozpočet se kontroluje před další cílenou extrakcí; otevřená otázka
zůstává bez návrhu a původní rozpoznaná fakta se zachovají.
Katalog zahrnuje všechny zdrojové otázky; karta a bezpečnostní triáž nejsou
zapojené. To není úplné pokrytí klinických problémů ani záruka záchytu LLM.
Nezávislou syntetickou regresi spouští `llm_intake.evaluate_topics`;
[příkaz a interpretace](../llm_intake/README.md#ověření-rozpoznávání-témat).

## Implementováno: větvení otázek a předání LLM výstupu

[Review a diagram](llm-flow.md) popisuje tok i dosavadní mezery. `Question`
je společný balíček otázky, všech možností, návodu, poznámky, pořadí a podmínky;
využívá jej model, katalog i pipeline. Příklady drží pouze ID a při sestavení
promptu dostanou aktuální balíček ze zdrojových definic. Výlučnost „žádné účinky“
je malá explicitní politika; směr škály se předává bez popisu barev.

`QuestionnaireFlow(questionnaire_id, targets=None)` načítá pořadí a `podminka`
z definic, nevytváří druhý ruční graf. Bez `targets` prochází celý formulář;
s `targets` začne vybranými otázkami a zahrne jejich potomky. Rodiče mimo
rozsah nevyplňuje. `QuestionnaireFlow.for_targets(targets)` navíc automaticky
odvodí dotazník z prvního zadaného cíle. `next_question()` vrací další balíček nebo None;
`record(session)` přijímá pouze očekávaný ukončený intake. Větve aktivuje
potvrzená odpověď, ne návrh. `snapshot()` rozlišuje ready, blocked, unresolved
a complete; None z `next_question()` samo neznamená dokončený sběr.

`find_question(question_id, questionnaire_id=None)` umožňuje dohledat otázku
ze všech dotazníků bez nutnosti předem znát ID dotazníku; při kolizi ID vyžaduje
upřesnění. `create_targeted_session(question_id)` připraví hotovou `Intake` relaci
pro cílenou udržovací otázku. Kořenový balíček `llm_intake` exportuje ucelené
rozhraní pro zprávu, extrakci, katalog, relaci i sestavení pipeline paketu.

`build_pipeline_packet(message, facts, sessions)` vrací JSON typu `llm_intake`
verze 1: původní podnět `message`, nepotvrzené `facts` a `question_answers`
s balíčky, hodnotami, potvrzením, citací a historií skutečných otázek/odpovědí.
Nový výstup neobsahuje barvy. Odmítnuté a nevyřešené návrhy mají null;
samostatný starší export intake v2 zůstává zachovaný. Časy tahů ani původ faktů
se nevymýšlejí. Při předání událostí je již uchovává, u původního `submit(text)`
zůstávají neznámé.

Původní CLI stále řeší jedinou otázku, nabízí `/moznosti` bez API volání a má
`--max-clarifications`. MASTER má samostatné CLI nad zaznamenanou zprávou výše.
Interaktivní MASTER a rozpočet kontaktu jsou implementované v `dialogue` výše.
Nový pipeline paket zatím nemá adaptér triáže ani karty. CLI jedné otázky
používá pouze minimální propojení s triáží popsané výše.

## Implementováno: malá deterministická triáž

`triage.py` obsahuje čistou funkci `evaluate_triage(data)` a CLI:

```text
uv run python triage.py vstup.json
```

Vytvořte UTF-8 soubor `vstup.json`, například:

```json
{
  "temperature_c": 38.2,
  "chemotherapy_within_6_weeks": true,
  "spo2_pct": 97,
  "overall_feeling": 3,
  "pain_nrs": 2,
  "pain_persists_after_rescue_dose": false
}
```

Kontext chemoterapie dodá aplikace z léčebných údajů; zahrnuje probíhající
chemoterapii nebo období do 6 týdnů po ní. LLM pouze převádí sdělená fakta,
neurčuje tento kontext klinickým odhadem. Teplota je kladné konečné číslo
ve °C, SpO2 číslo 0–100 %, pocit celé číslo 1–5 (5 = velmi špatně),
bolest celé číslo NRS 0–10. Kontext chemoterapie a přetrvávání bolesti po
SOS dávce jsou boolean. Není-li známo, zda SOS dávka byla užita a zabrala,
`pain_persists_after_rescue_dose` musí být `null`, nikoli `false`.

Všechna pole lze vynechat nebo nastavit na `null`; neznámá hodnota se nenahradí
nulou. Prototyp předpokládá správně připravený JSON s typy a rozsahy uvedenými
výše. Nemá vlastní validátor ani obsluhu výjimek; chyby souboru, JSON nebo typů
nechává zobrazit přímo Python. Výsledek vypisuje jako JSON na stdout.

Implementované podmínky podle pravidel balíčku, oddíly 3–4:

- Červená: teplota ≥ 38 °C v kontextu chemoterapie nebo SpO2 < 90 %.
- Oranžová: SpO2 < 92 %, pocit 5 nebo bolest NRS ≥ 7 přetrvávající po SOS dávce.
- Žlutá: bolest NRS 4–6.
- Platí nejvyšší aktivovaná úroveň; zelená znamená jen absenci nálezu v této sadě.

Každé kritérium má vlastní funkci: `fever_score`, `oxygen_score`,
`overall_feeling_score`, `pain_score`. Funkce vrací 1–4 (green až red),
případně `None`, když nelze kritérium uzavřít. Úrovně jsou `Severity(IntEnum)`:
`GREEN = 1`, `YELLOW = 2`, `ORANGE = 3`, `RED = 4`. `evaluate_triage` spočítá
maximum známých skóre. Skóre se nesčítají.
Každá funkce má anglický docstring s odkazem na soubor a konkrétní oddíl pravidel.
V JSON se enum automaticky zapíše jako číslo; barva zůstává anglický řetězec.

Výstup obsahuje `color`, `scores` (skóre jednotlivých kritérií) a
`requires_review`. Nahrazuje předchozí výstup s textovými důvody a seznamem
chybějících polí. `null` ve skóre označuje kritérium k posouzení. Pokud jsou
známá skóre jen zelená a jiné kritérium není vyřešené, výsledná barva je
`null`. Prokázaná vyšší barva zůstává minimem i při neúplných údajích.
Silná bolest bez potvrzeného přetrvávání po SOS dávce zůstává k posouzení.

Jde o omezenou sadu, nikoli úplnou triáž ani klinicky ověřený systém.
Zatím nezpracovává zimnici, pokles saturace proti obvyklé hodnotě, další
příznaky, trendy ani kontakty. Načítání historie ani napojení na `llm_intake/`
nejsou v triáži zapojené.
Zdroj: [pravidla triáže](../rakathon_meddi_onco_data/docs/pravidla_triaze.md),
oddíly 3–4. Rozšiřování pravidel bude pokračovat po review tohoto souboru.

## Samostatný modul LLM intake

Cílený klient z banky třinácti příkladů posílá nejvýše tři: nejprve shodnou
otázku, pak stejný typ. Výběr nezávisí na textu odpovědi a zachovává stabilní
prefix. `Client(on_usage=callback)` umožňuje odečíst skutečné tokeny, cache,
reasoning a dobu volání bez logování obsahu; nastaví se například přes
`dataclasses.replace(Client.from_env(), on_usage=callback)`. Chybějící
metriky jsou null. Evaluátor je připojuje do `api_usage` reportu.
Rozhraní klinického paketu se tím nemění.

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.evaluate_topics --cases tests/fixtures/master_precision_cases.json --output .scratch/master-precision.json
```

Vedle minimálního pokrytí evaluátor umí `allowed_topics` a `fact_checks`.
Nepovolená témata, nesprávný subjekt, negace nebo hodnota jsou neúspěch;
`topic_precision` má jmenovatel jen na plně označené sadě. Měření tokenů
a jeho limity popisuje [README modulu](../llm_intake/README.md#spotřeba-tokenů).

[llm_intake/README.md](../llm_intake/README.md) popisuje CLI, Python API,
konfiguraci a export `schema_version=2`. Modul používá jednu explicitně vybranou
otázku z definic: slovní odpověď → přiřazení k interní možnosti → pacientovo
potvrzení slovního znění nebo oprava. Při nejasnosti LLM položí krátkou navazující
otázku podle chybějícího rozlišení možností; neopakuje celý dotaz. Kontext zahrnuje
otázky i odpovědi. Výchozí limit dvě doptání řídí kód; bez vyřešení zůstane stav
`unresolved`, bez vymyšleného výběru. Export obsahuje historii a počty tahů.
Pacient předem nevidí možnosti ani barvy.
Stav drží Python; potvrzení nevytváří LLM. Kolegové se napojují přes `Intake`
a potvrzený JSON, bez závislosti na CLI. Nejde zatím o obecné schéma karty pacienta.

Výchozí model je `gpt-6.1-sol`, jeho deployment `gpt-6-1-sol-dz-eu` se nastavuje
přes `MEDDI_LLM_MODEL`. Dodaná brána vyžaduje `MEDDI_LLM_KEY_HEADER=api-key`.
Adaptér používá dodanou OpenAI kompatibilní bránu a Chat Completions se striktním
JSON schématem. Implementace používá jen standardní knihovnu, `pyproject.toml`
a `uv.lock` nebylo potřeba měnit. Klíč v `MEDDI_LLM_API_KEY` se načítá z prostředí;
lokální `llm_intake/.env` lze načíst přes uv a Git ho ignoruje.

```text
uv run python -m llm_intake --list
uv run --env-file llm_intake/.env python -m llm_intake --question unava
uv run python -m pytest tests/test_llm_intake.py -q
```

Rozsah: jedna otázka a potvrzovací cyklus; průchod podmíněnými otázkami,
pacientská karta, časování a triáž zůstávají oddělené. Testy nahrazují LLM i HTTP
transport. Živé volání brány se syntetickou odpovědí je ověřené; systematické
měření kvality modelu zůstává další krok. Export přidává `signaly_odpovedi`:
původní barvy možností načítá deterministicky kód, nejsou výslednou triáží.
V CLI se interní JSON vypisuje pouze s `--debug`, Python rozhraní jej vrací přímo.
Nový kontrakt extraktoru: `extract(question, source_messages, source_questions)`.
Pro současný počet možností nepřidáváme RAG ani embeddingy. Správnost přiřazení
a nutnost doptání budeme měřit na označených scénářích; skóre podobnosti ani
nekalibrované procento LLM zatím nepoužíváme jako rozhodovací práh.

## Směr určený týmem

- První verze je CLI proof of concept. Prioritou jsou data, dotazování,
  vyhodnocování odpovědí a funkční průchod. Frontend, vizuál a nasazení odkládáme.
- Každý pacient má kartu aktuálního stavu zohledňující vývoj v čase. Karta
  poskytuje kontext dotazování a slouží také zdravotníkovi.
- LLM personalizuje otázky a interpretuje subjektivní odpovědi. Pomocí instrukcí
  a příkladů v kontextu je převádí do strukturovaných dat.
- Veškerou triáž provádí náš kód. LLM neurčuje ani nenavrhuje úroveň,
  doporučený krok, kontakt nebo upozornění týmu; potvrdil tým 16. 10. 2026.
- Systém reaguje na nové informace, plánuje další kontakt, poskytuje zpětnou
  vazbu a podle stavu upozorní tým. První CLI používá simulovaný čas a přehrávání
  událostí s předem zaznamenanými odpověďmi; potvrdil tým 16. 10. 2026.

## Rozdělení odpovědnosti

Následující text popisuje cílové propojení; aktuální rozsah samostatných modulů
je uveden výše.

LLM převádí volný text na pozorování s vazbou na zdroj. Výstupní schéma
extrakce neobsahuje triážní rozhodnutí. Strukturované odpovědi dotazníků
a měření zpracovává přímo kód; není třeba je znovu interpretovat modelem.

Kód validuje pozorování, aktualizuje kartu a vyhodnocuje pravidla nad kontextem
léčby a historií. Pokrývá tvrdá pravidla i kontext, trendy, rozpory, chybějící
údaje a neodpovědi. Určí úroveň, další krok, kontakt podle pracovní doby
a upozornění týmu; vysvětlení odvodí ze spuštěných pravidel a jejich vstupů.
Převod kontextových pravidel do konkrétních podmínek zbývá upřesnit s mentorem.

Při dotazování kód určí potřebné informace a čas kontaktu, LLM personalizuje
formulaci. Nevalidní nebo nejasná extrakce je samostatný stav zpracování,
nikoli důkaz nízkého rizika. Postup při nejistotě a výpadku určí kód.

## Dostupný balíček a první režim

V [rakathon_meddi_onco_data/](../rakathon_meddi_onco_data/README.md) je lokálně
14 fiktivních pacientů a 171 check-inů (ověřeno načtením JSON 16. 10. 2026).
`pacienti/` jsou vstupy, `ground_truth/` jsou reference párované přes `checkin_id`.
Očekávaný výstup popisuje README balíčku, oddíl 4. To je první kontrakt našeho
vyhodnocení; případné dodatečné požadavky poroty zbývá potvrdit.

Návrh pro první CLI: přehrát zaznamenané události v jejich čase, vytvořit kartu,
vyhodnotit stav a zapsat návrh další otázky včetně důvodu a času kontaktu.
Historickou odpověď nepřiřazovat libovolné nově vygenerované otázce. Pokud nová
otázka nemá ve scénáři odpověď, ponechat ji otevřenou; nedoplňovat ji LLM
ani budoucím záznamem. Interaktivní rozhovor tím zatím není plně ověřen.

Z rozhodovacího kontextu vyloučit `nazev_scenare`, který není reálným vstupem
(README balíčku, oddíl 5), i veškeré reference. Časově filtrovat také laboratoř,
vyšetření, události týmu a změny léčby. U volných poznámek a výchozích souhrnů
nejprve ověřit, zda neprozrazují budoucí vývoj. Dostupnost výsledku nemusí být
totožná s časem odběru; význam časových polí je třeba dořešit při tvorbě adaptéru.

Pro prototyp nad smyšlenými daty organizátor povoluje libovolný LLM
(README balíčku, oddíl 6). Výchozího kandidáta a adaptér popisuje modul výše. Klinická pravidla
bereme z dodaných podkladů; kvalifikované lidské ověření zůstává nutné.

## Zpřesnění k diskusi

**Historie a karta:** uchovat původní události, jejich autora, čas vzniku
i čas dostupnosti systému. Kartu chápat jako odvozený pohled, který lze obnovit
z historie; LLM navrhuje strukturovaná pozorování, nepřepisuje celou kartu.
U každého zjištění zachovat zdroj, čas a zda jde o výslovné sdělení, nebo odhad.
Chybějící údaj, popřený příznak a rozpor jsou různé stavy.

**Obsah a čas dotazu:** nejprve určit důvod kontaktu a potřebné informace
(pravidelná kontrola, upřesnění, sledování otevřeného problému). LLM navrhne
srozumitelnou formulaci. Časování, počet otázek, opakování a reakci na neodpověď
řídit explicitní politikou podle podkladů mentora. Nová spontánní zpráva musí
spustit vyhodnocení i mimo plánovaný kontakt. Známý urgentní signál nesmí čekat
na dokončení rozhovoru. Neodpověď sama nepotvrzuje stabilní zdravotní stav.

**Strukturovaná extrakce:** příklady v kontextu doplnit pevným schématem,
strukturou vynucenou API tam, kde je dostupná, a lokální validací. JSON
odpovídající schématu ještě nedokládá správné porozumění zprávě; kontrolovat
také vazbu na původní text, jednotky, čas a negace. Nevalidní výstup nebo výpadek
LLM nesmí potichu aktualizovat kartu ani být považován za úspěšné vyhodnocení.
Technický podklad: [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
ověřeno 16. 10. 2026; jde o příklad možnosti API, poskytovatele tím nevybíráme.

**Ověření:** zvlášť hodnotit extrakci, triáž a užitečnost dotazování. Historická
data ověří zpracování zaznamenaných zpráv, ale nemusejí obsahovat odpovědi
na nově vytvořené otázky. Pro interaktivní část připravit scénář s člověkem
nebo simulátorem; výsledek LLM simulace není nezávislá klinická reference.
Tým zvolil simulované hodiny a předem zaznamenané odpovědi. Adaptivní dotazování
proto zatím hodnotíme jako návrhy otázek, nikoli jako ověřený uzavřený rozhovor.

Otevřeno: konkrétní obsah karty, schéma extrakce a časovací politika.
Definice existujících dotazníků je v `rakathon_meddi_onco_data/docs/dotazniky_definice.json`.
Barvy odpovědí nejsou výsledná kontextová triáž (README balíčku, oddíl 4).
Tvrdá pravidla určují minimální úroveň; při rozporu se systém doptá a do té
doby počítá s horší variantou ([pravidla](../rakathon_meddi_onco_data/docs/pravidla_triaze.md),
oddíly 3 a 6). To jsou požadavky zadavatele, nikoli volitelná preference architektury.

## Návrh k společnému projití

Jeden lokální proces s oddělenými kroky zatím stačí. Nejprve ověříme tento tok
na jednom pacientovi; konkrétní soubory a rozhraní určíme podle dodaného JSON.

1. **Vstup a čas:** načíst kontext pacienta a události dostupné k okamžiku `t`.
   Oddělit reference pro hodnocení, aby neunikaly do rozhodování ani souhrnu.
2. **Porozumění zprávě:** spojit dotazník, měření a text s odkazy na původní
   záznamy. Zachovat čas, autora, chybějící údaje a rozpory. Zde může pomoci LLM.
3. **Triáž v kódu:** použít pravidla dodaná a potvrzená mentorem i dosavadní
   vývoj. Vrátit úroveň 1–4, důvody a podklady. LLM dodává pouze extrahovaná
   pozorování; triážní rozhodnutí vytváří výhradně kód.
4. **Výstup:** pacient dostane srozumitelný další krok, zdravotník prioritu
   a krátký souhrn s časovou osou. V demu předání upozornění simulujeme.
5. **Vyhodnocení:** přehrát stejné případy v čase a porovnat s oddělenými
   referencemi. Sledovat podhodnocení červené, záchyt oranžové/červené a počet
   zbytečných poplachů. Jednotku hodnocení a opakovaná upozornění vyjasnit
   podle hodnoticího rozhraní zadavatele.

Časové přehrávání a lidský dohled vyžaduje [zadání MEDDI](<../documents/MEDDI – MEDDI Onco.pdf>),
s. 7 a 10. Rozdělení komponent výše je náš návrh, ne předepsaná architektura.

## Co rozhodneme postupně

- Nad JSON: schéma událostí, dostupnost informací v čase, referenční výstup.
- Nad jedním případem: schéma extrakce, podmínky pravidel a chování při chybě
  a nejistotě. Rozdělení odpovědnosti LLM / triáž v kódu je již rozhodnuté.
- Po funkčním průchodu: jednoduché UI, ukládání stavu a způsob předvedení.
- Nakonec: popis budoucí integrace MEDDI. API na akci není (zadání, s. 12).

API adaptér je ověřený na dodané bráně se syntetickou odpovědí. LLM dostává
pouze jednu otázku, interní texty možností a odpovědi k ní, nikoli barvy.

## Příkazy

Platí v Linuxu i Windows PowerShellu z kořene repozitáře:

```text
uv sync --locked
uv run ruff check .
uv run pytest
```

Testy pytest existují pro `llm_intake/`. Ověření prvního `triage.py`
proběhlo samostatnými kontrolami funkce a CLI; rozsah a výsledek jsou v tasks.md.
CLI intake navíc vypisuje omezenou triáž podle propojení popsaného výše.

## Historický režim porovnání barev dotazníků s referencemi

Z `origin/main` pochází také `meddi/form.py`, `meddi/loader.py`,
`meddi/common_types.py`, `meddi/triage.py` a porovnávací CLI `main.py`.

```text
uv run python main.py
uv run python -m meddi.triage vstup.json
```

Dřívější `main.py` porovnával maximum barev dotazníků. Od `d1b58f4`
standardně porovnává výsledek strukturovaných pravidel; původní barva
dotazníku je pouze vedlejší údaj. Aktuální přepínače popisuje oddíl
„Porovnání ground truth a pravidel po check-inech“ výše. Reference zůstávají
mimo rozhodovací vstupy. Výsledky porovnání nejsou klinickým ověřením.
