# Kontrakt triáže

Klinická pravidla jsou v `meddi/triage.py` a `meddi/clinical_rules.py`;
normalizace v `meddi/form.py`, mapování kontaktu v `meddi/pipeline.py`,
pokrytí odpovědí v `meddi/answer_coverage.py` a výstupní politika
v `meddi/disposition.py`. Web ani LLM nezavádějí další klinické prahy.
Zdroj: [pravidla pořadatele](../rakathon_meddi_onco_data/docs/pravidla_triaze.md),
zejména §3–6. Nejde o klinicky schválenou implementaci.

## Vstupy a rozhraní

```python
from meddi.pipeline import evaluate_contact

assessment = evaluate_contact(
    packet,                    # llm_intake / schema_version 1
    patient_snapshot=snapshot, # aktuální údaje karty, nikoli celý pacient
    now="2026-10-17T10:00:00+02:00",
)
```

Paket dodává `MasterDialogue.snapshot()` nebo `build_pipeline_packet()`;
[LLM kontrakt](../llm_intake/MASTER_CONTRACT.md). Potvrzené odpovědi se validují
proti původním definicím. Přesně doložený fakt může aktivovat pravidlo ještě
před potvrzením, ale jeho `confirmation=unconfirmed` se nepřepisuje.
Nepotvrzená možnost v `question_answers` není vybraná odpověď.

Snapshot má pouze `patient_id`, `as_of`, `context`, `observations`:

```json
{
  "patient_id": "synthetic-patient",
  "as_of": "2026-10-17T10:00:00+02:00",
  "context": {"chemotherapy_within_6_weeks": true},
  "observations": {
    "temperature_c": {
      "value": 36.5,
      "unit": "degC",
      "observed_at": "2026-10-17T09:00:00+02:00",
      "source": "synthetic-measurement"
    }
  }
}
```

Snapshot vyžaduje stejné ID pacienta a `as_of` s pásmem. Položka může být
přímá hodnota nebo `{value, unit?, source?, available_at?, observed_at?, valid_until?}`.
Výchozí dostupnost je `as_of`, výchozí pozorování jeho dostupnost; přesnější
čas musí dodat producent karty. Povolená pole určují `CONTEXT_FLAGS`,
`OBSERVATION_FLAGS`, `OBSERVATION_NUMBERS` v `clinical_rules.py`, navíc
`pain_nrs`, `overall_feeling`, `pain_persists_after_rescue_dose`.
Argument `context` je explicitní aktuální vstup; léčebné příznaky přepisují
snapshot. Neznámé pole v explicitním kontextu/snapshotu je chyba vstupu.

Strukturovaná cesta:

```python
from meddi.patient_inputs import build_triage_inputs
from meddi.triage import evaluate_checkin

prepared, context, observations = build_triage_inputs(patient, checkin)
assessment = evaluate_checkin(prepared, context, observations)
```

`prepare_checkin` zachovává odpovědi, neobarvené/negativní údaje, měření,
zprávu i přílohy. Barvy možností počítá z definic, nikoli z uložené barvy.
`non_green_answers` jsou zdrojové signály, ne konečná triáž.
`build_triage_inputs` omezuje historii časem a připraví vybrané trendy;
neinterpretuje zprávy, poznámky, laboratoře, vyšetření nebo zásahy týmu.

Kořenové `triage.evaluate_pipeline_packet` a `evaluate_intake` delegují do
společného adaptéru. Plochý `evaluate_triage(data)` zachovává omezený rozsah
čtyř kritérií, a proto nenahrazuje kompletní check-in.

## Mapování a validace

- `NUMERIC_FACTS` a `FLAG_FACTS` v `pipeline.py` určují podporované koncepty;
  například `temperature` → `temperature_c`, `spo2` → `spo2_pct`,
  `pain.nrs` → `pain_nrs` a `confusion` → `confusion`.
- Počty zvracení/průjmu potřebují doložené 24hodinové okno; celkový počet
  stolic není nárůst proti normálu. Současné mapování zvracení uznává také
  přesné znění původní otázky; před personalizací je nutné použít ID/metadata.
- Negace logického příznaku znamená `false`, negace měření nevytváří nulu.
  Potíže pečujícího nepatří pacientovi; `caregiver_exhaustion` je vlastní vstup.
- Nepodporovaný koncept/interval, nejistota, neurčený subjekt nebo nevyřešený
  čas zůstávají v `unprocessed_facts`. Téma otázky neprokazuje podmínky pravidla.
- `meddi/validation.py` odmítá NaN, nekonečno, boolean místo čísla, neplatnou
  doménu či jednotku. `degC` je podporováno. Chyba vyvolá výjimku, ne negativní nález.

## Čas a rozpory

Výchozí `now` je poslední dostupnost zprávy, nikoli systémové hodiny.
Přehrávání dodává explicitní čas. Platí `observed_at <= available_at`;
všechny explicitní časy vyžadují pásmo. Budoucí/expirované vstupy zůstávají
v `deferred_inputs`, budoucí snapshot nebo jiný pacient se odmítnou.

Pro parametr se vybere nejnovější známý čas pozorování; současné konfliktní
hodnoty zůstanou všechny a pravidla zachovají vyšší doložené riziko.
Při chybějícím čase vznikne `unknown_observation_time`. Není to maximum celé
historie. Rozsah možnosti a přesné měření sdílejí parametr, ale neporovnávají
se jako stejné číselné reprezentace. V režimu
`dialogue.mode=targeted_from_message` se navíc zachovávají aktuální
fakta úvodní zprávy spolu s novějšími volbami. Pozdější mírnější volba sama
neprokazuje odeznění úvodního měření; opačné podklady nezmizí z pravidel.
Dřívější uložené pakety `questionnaires_from_message` se pro kompatibilitu
čtou stejně; nový dialog je nevytváří.

`time_text` i citace se ověřují proti originálu. Adaptér podporuje omezený
seznam současných/24hodinových vyjádření a výslovné „od včera“.
Doložená délka (`hours_without_diarrhea`, `hours_without_urine`,
`nosebleed_minutes`, `constipation_days`) se nepovažuje za historický timestamp.
Jednotky délky se kontrolují, nedopočítává se neurčené 24hodinové okno. „Od rána“ není automaticky 24 hodin;
obecné relativní časy a klinická expirace zůstávají otevřené. Bez časového
výrazu se fakt vztahuje k dostupnosti zdrojové zprávy.

## Výstup

Kontakt vrací `kind=meddi_contact_assessment`, `schema_version=1`.
Verzi pravidel určuje `TRIAGE_RULES_VERSION` v `meddi/triage.py`.

| Pole | Význam |
| --- | --- |
| `minimum_color` | Doložené a výslovně předběžné minimum, oddělené od úplnosti |
| `color`, `uroven` | Výsledná green/yellow/orange/red a úroveň 1–4 |
| `assessment_status`, `requires_review`, `needs_clinical_review` | Úplnost a potřeba dořešit dodané údaje; nejsou náhradou priority |
| `scores`, `reasons` | Výsledky pravidel, zdroje, důkazy a případné `provisional`/`uncertainty_source` |
| `non_green_answers`, `review_issues`, `skipped_rules` | Zdrojové signály, problémy a konkrétní chybějící podmínky |
| `adapter_issues`, `unprocessed_facts`, `deferred_inputs` | Rozpory, nepokryté významy a časově vyloučené údaje |
| `triage_inputs`, `intake` | Zmrazené vstupy jádra a kopie celého zdrojového kontaktu |
| `evaluated_at`, `rules_version` | Čas hodnocení a verze politiky |
| `doporuceny_krok`, `doporuceny_kontakt`, `doporuceni_pro_pacienta` | Pevná výstupní politika, zatím obecná kontaktní instrukce bez vypočteného termínu |
| `upozornit_tym`, `action_source` | Požadavek akce a zdroj; funkce nic neodesílá |
| `care_context` | Zdrojovaný kontext explicitní symptomatické paliativní péče pro společnou výstupní politiku; 2/3 mají 24h paliativní tým/hospic a záložní 155, červená se nesnižuje (S4 §5) |

`resolve_disposition` ponechá vyšší minimum; relevantní nevyhodnocené vstupy
předá nejméně jako žluté. Samotné chybění všech hypotetických příznaků není
poplach. Barva možnosti sama nezvyšuje klinické minimum. Nepokrytá odpověď zůstává
ve `review_issues` a `non_green_answers`; výstupní politika ji předá k review
(typicky yellow), nikoli automaticky red podle zobrazovací škály ESAS.
Nejde o schválené mapování škál na klinické stupně.
Kladná MASTER odpověď se upřesňuje přes existující škálu; po potvrzení
pipeline vrací `clarified_facts` s vazbou na skutečnou cílenou odpověď.
Textový obecný pocit není odhadnuté číslo ani popření příznaků. Jeho
upřesnění neodstraňuje jiné nevyhodnocené/nejisté údaje ani známé minimum.
Plošný převod prázdných/nejistých vstupů na zelenou zůstává zakázaný.
`unresolved_concepts` rozlišuje skutečně nepokryté pojmy od validovaných
vstupů jádra bez navazující otázky; původní paket se nepřepisuje.
Doložené příznaky s neznámým rizikovým kontextem mohou mít vyšší možné minimum.
To není potvrzení domyšleného údaje ani klinicky ověřený převod škál.

Červená a neúplnost se nevylučují. `skipped_rules` nemají vytvářet desítky
otázek bez posouzení relevance. Karta musí zachovat původní události a revize;
`triage_inputs` nejsou náhrada originálu. Aktuální webový přepočet starých
výsledků používá jen zmrazené vstupy, nikoli dnešní historii pacienta.

## Otevřené klinické otázky

| ID | Závislost před dokončením | Zdroj / další práce |
| --- | --- | --- |
| O1 | NRS: text 0–10 proti typu/poznámce 1–10; backend přijímá nulu, cílený Intake ne | S5 `bolest_analgeticka_terapie/nrs`; nulu zachovat, nepřevádět na 1 |
| O2 | Průjem: tvrdé minimum ≥7 proti možnosti >7; první možnost nepopisuje všechny nízké počty | S4 §3–4, S5 `prujem`; přesný počet nad baseline a 24h okno zachovat samostatně |
| O3 | ESAS/psychoškály a obecné omezení činností nemají doložený univerzální převod na klinický stupeň | S4 §4, S5; získat klíč screeningu a schválit mapování, včetně neuropatie, kloubů a kožních obtíží |
| O4 | Podložené alternativy, intervaly a relevantnost nejistoty nejsou úplně implementované | S4 §6.4; neodhadovat přesnou hodnotu ani nedělat poplach z každého chybějícího pole |
| O5 | Obecný trend, obvyklý stav a uzavření epizody po zásahu nemají úplný algoritmus | S4 §5, §6.1/§6.3; samotné převzetí alertu nesnižuje závažnost |
| O6 | Párové prahy tlaku mají v kódu výklad OR; zdroj neurčuje výslovně AND/OR ani číselný práh „vysoký tlak + příznaky“ | S4 §3–4; kód používá explicitní `high_blood_pressure`, nevnášet další práh |
| O7 | Skutečné podání, D1, vícedávkové/orální režimy a dostupnost dat bez času | S3 §5, S4 §3/§5; úplnost léčby, dostupnost laboratoře versus čas odběru |
| O8 | Intervaly kontrol/přeměření, expirace a postup při neodpovědi nejsou úplné | S4 §2–6; termíny určí schválená politika nebo tým |
| O9 | Provozní kalendář, hranice pracovní doby, zvláštní žluté lhůty a reálné paliativní kontakty | S4 §2/§4–5; potvrdit s pracovištěm |
| O10 | Jádro i úzká offline návaznost implementované; obecné řízení epizod otevřené | [Upřesnění O10](#upřesnění-mentora-k-o10): selhání příjmu nebo udržení tekutin z libovolné příčiny + známky dehydratace znamená 4. Regrese skutečného offline replay ONC-011 C08 → 3, C09 → 4, včetně přejmenování ID, budoucích údajů, zlepšení a obnovení pití |

S3–S5 označují [zdroje zadání](challenge.md#zdroje-a-jejich-platnost).
Zobrazovací barva ESAS není NRS ani CTCAE stupeň. Nezavádět práh psychoškály
podle jediného referenčního případu ani plošně mapovat index odpovědi na stupeň.
Přetrvávání neuropatie, jemná motorika, doba posledního průjmu a účinek SOS
musí být doložené, nikoli odvozené jen z podobné otázky.

### Upřesnění mentora k O10

Zdroj: komentář mentora k ONC-011-C09, doslovně předaný uživatelem v této
konverzaci 17. 10. 2026. Jde o doplnění původního S4 §3 / Červená / Zvracení
a Příjem a tekutiny; původní organizátorský soubor zůstává zachovaný.

> Máte pravdu, že pravidlo bylo nešťastně zařazené jen pod zvracení. Červená je tu postavená na této kombinaci:
>
> pacient nepřijme nebo neudrží tekutiny (z jakéhokoli důvodu: zvracení, bolestivé polykání, mukozitida), tady to bylo doložené už předchozí den,
> a zároveň má známky dehydratace: málo močí, závrať, tep nad 100.
> Taková kombinace je 4 vždy, a na cisplatině nebo jiné nefrotoxické léčbě o to víc (riziko akutního selhání ledvin). Samotné „málo močím a točí se mi hlava“ bez doloženého selhání příjmu tekutin zůstává podle pravidla 3.

Pro ověření případu jsou vstupní důkazy dostupné již v čase C09:
`pacienti/ONC-011.json`, C08 (16. 9. 08:00): „Nepolknu skoro nic, ani vodu moc ne,
sliny vyplivuju.“; C09 (17. 9. 06:50): „Včera jsem vypil možná půl litru.
Točí se mi hlava, málo močím.“ a tep 112/min. Týmová hospitalizace z 17. 9.
12:00 do tohoto hodnocení nevstupuje. Jde o zdrojované posouzení konkrétní
epizody, nikoli o domyšlenou anurii nebo automatické převzetí každého staršího
nálezu. Mentor tímto neurčil obecnou dobu platnosti historického příznaku.

Další upřesnění předané uživatelem 17. 10. 2026 výslovně zahrnuje také
systolický tlak pod 90. Implementace `fluid_intolerance_with_dehydration`
(verze pravidel 7) kombinuje `cannot_keep_fluids` nebo `cannot_drink_fluids`
s alespoň jednou známkou: `low_urine`, `dizziness`, `orthostatic_dizziness`,
`pulse_bpm > 100`, `systolic_bp < 90`; zachovává i dříve podporované
`dehydration_signs` a `hours_without_urine > 10`. Nemožnost příjmu sama
znamená 3. Snížený příjem s málem moči nebo závratí zůstává 3.
Léčba cisplatinou není nutná podmínka červené a její nepřítomnost nesnižuje
úroveň. Prompt extrakce rozlišuje nemožnost příjmu od pouhého snížení.

`tests/test_dehydration_clarification.py` ověřuje kombinace, hranice,
cisplatinu i aktuální/expirující/budoucí/odeznělý údaj v pipeline snapshotu
bez LLM. Nový úzký parser `meddi/fluid_intake.py` přes `build_triage_inputs`
rozpozná vybraná výslovná sdělení pacienta (nikoli první osobu pečujícího).
Naváže selhání příjmu z nejbližšího předchozího check-inu předchozího
kalendářního dne, jen pokud aktuální pacient znovu popisuje včerejší pití
a dotazník dokládá trvající těžkou poruchu polykání (afty index 3).
Obnovené pití, mírnější porucha, chybějící historické selhání nebo jiný den
neaktivují tuto návaznost. Zdroj má citaci i obě check-in ID; rozhodování
nečte reference, ID ani názvy scénářů. Skutečný ONC-011 má C08 → 3, C09 → 4
v offline regresi; obecné porozumění jazyku a řízení jiných epizod tím není
vyřešené. Úzká návaznost vychází z mentorova konkrétního upřesnění, její
klinické zobecnění na jiné průběhy zůstává součástí lidského převzetí.
Z mentorova příkladu se neodvozuje samostatné pravidlo
„tep nad 100 = dehydratace“ ani „snížený příjem = nemožnost přijímat tekutiny“.

## Původ mapování léčiv

`DRUG_CLASSES` v `patient_inputs.py` je omezené ruční mapování názvů,
nikoli úplný lékový číselník. Neznámý název neprokazuje nepřítomnost léčby.
Odvození nedávné chemoterapie používá rozpoznané léky a D1 cyklů do 42 dnů;
nenahrazuje evidenci posledního skutečného podání. Zůstává nutné klinické review.

Podklady k revizi mapování (nepřidávají nové triážní prahy):

| Oblast | Zachovaná opora |
| --- | --- |
| Názvy/skupiny výslovně uvedené v pravidlech | S4 §3–5 |
| Doxorubicin a morfin | [EMA Caelyx](https://www.ema.europa.eu/en/medicines/human/EPAR/caelyx-pegylated-liposomal), [EMA opioidy](https://www.ema.europa.eu/en/medicines/human/referrals/modified-released-oral-opioids) |
| Fluorouracil, kapecitabin a oxaliplatina | [EMA Xeloda](https://www.ema.europa.eu/en/medicines/human/EPAR/xeloda) |
| Cyklofosfamid, vinkristin a etoposid | [NCI Ewing – chemoterapie](https://www.cancer.gov/types/bone/hp/ewing-treatment-pdq) |
| Cisplatina, karboplatina a irinotekan | [NCI cisplatina](https://www.cancer.gov/about-cancer/treatment/drugs/cisplatin), [NCI CanMED](https://seer.cancer.gov/oncologytoolbox/canmed/ndconc/69339-0367/), [NCI irinotekan](https://www.cancer.gov/about-cancer/treatment/drugs/irinotecanhydrochloride) |
| Nivolumab, ipilimumab a atezolizumab | [EMA Opdivo](https://www.ema.europa.eu/en/medicines/human/EPAR/opdivo), [společné hodnocení](https://www.ema.europa.eu/en/documents/withdrawal-report/withdrawal-assessment-report-opdivo-and-yervoy-ws1372_en.pdf), [hodnocení HCC](https://www.ema.europa.eu/en/documents/variation-report/opdivo-h-c-ws-2717-epar-assessment-report-variation_en.pdf) |

Pro význam stupňů zachovat [NCI CTCAE v5](https://dctd.cancer.gov/research/ctep-trials/for-sites/adverse-events/ctcae-v5-8x11.pdf):
úzkost s. 109, artralgie s. 89, periferní neuropatie s. 104, hypertenze s. 145;
a [NCI PRO-CTCAE FAQ](https://healthcaredelivery.cancer.gov/pro-ctcae/faqs.html)
k rozlišení pacientského skóre a klinického stupně. Jde o podklady pro
kvalifikované ověření, nikoli schválený automatický převod. Odkazy se při
úklidu dokumentace nově neověřovaly online.

## Zpráva původního check-inu

`meddi.messages.evaluate_message_checkin(patient, checkin, extract=None,
analysis=None)` používá stejný MasterExtractor a jádro jako nový kontakt.
Extraktoru předá pouze skutečnou zprávu, autora a otázku; nedostane pacientský
soubor, budoucí historii ani reference. Volitelný `clinical_fields` v promptu
pojmenovává vstupy existujících pravidel, neurčuje diagnózu ani úroveň.
`analysis` uchovává MessageEvent a fakta; musí přesně odpovídat originálu.
Čas původního check-inu je Europe/Prague. Samotný GET reportu nic neextrahuje.

`evaluate_contact` nově přijímá `prepared_checkin`: validuje pacienta/contact ID,
připojí hotové odpovědi a vitální funkce, zachová zdroje a chybějící odpovědi.
Obsah zprávy projde lokální validací; její vynechání symptomu není popření.
Interval/počet bez okna může doložit přítomnost potíže, ne přesné 24h měření
nebo nárůst proti normálu. Při průjmu na irinotekanu bez doloženého intervalu
zůstává výslovně předběžné yellow (§5/§6.4); nevymýšlí se interval <12 h.

Výstup doplňuje `message_analysis_status` (complete/failed/not_present),
`message_analysis`, `message_conflicts`, `follow_up_questions`. Doptání je
návrh pro člověka, historické odpovědi na něj se nevyrábějí. Chyba API nebo
nevalidní extrakce zachová původní text, strukturované minimum a review;
nevydává se za úspěšnou prázdnou zprávu. Při současném rozporu platí horší
podložená varianta podle pravidel §6.2–4; metadata rozporu zůstávají dostupná.
Úplné klinické pokrytí a řešení explicitních oprav v čase zůstávají M3/K7.
