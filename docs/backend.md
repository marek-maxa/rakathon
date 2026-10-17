# Společný výpočetní backend

Implementováno 17. 10. 2026. Jediná sada klinických pravidel je v
`meddi/triage.py` a `meddi/clinical_rules.py`. Nový adaptér nevolá LLM ani
nepřidává klinické prahy. Web, ukládání karty a plánování kontrol jsou další kroky.

## Rozhraní

```python
from meddi.pipeline import evaluate_contact

assessment = evaluate_contact(
    packet,                       # llm_intake / schema_version 1
    patient_snapshot=snapshot,    # volitelné aktuální údaje karty
    now="2026-10-17T10:00:00+02:00",
)
```

`packet` je nezměněný výstup `build_pipeline_packet()` nebo `MasterDialogue`.
Funkci lze zavolat po každé nové zprávě i po potvrzení. Nečeká na dokončení
dialogu: přesně doložený rizikový fakt může spustit pravidlo před potvrzením,
ale jeho zdrojový stav nadále zůstává `unconfirmed`. Nepotvrzený návrh odpovědi
z `question_answers` se naopak jako vybraná možnost nepoužije.

`patient_snapshot` je **aktuální výběr údajů**, nikoli celý pacientský soubor
nebo neomezená historie. Producent karty vybere relevantní epizodu a kontext.
Příklad [syntetického snapshotu](../meddi/snapshot.example.json):

```json
{
  "patient_id": "synthetic-patient",
  "as_of": "2026-10-16T10:00:00+02:00",
  "context": {"chemotherapy_within_6_weeks": true},
  "observations": {
    "temperature_c": {
      "value": 36.5,
      "unit": "degC",
      "observed_at": "2026-10-16T09:00:00+02:00",
      "source": "synthetic previous measurement"
    }
  }
}
```

Snapshot musí mít stejné `patient_id` jako kontakt a čas `as_of` s časovým
pásmem. Číselné a logické položky mohou být přímo hodnotou nebo záznamem
`{value, unit?, source?, available_at?, observed_at?, valid_until?}`.
Výchozí dostupnost záznamu je `as_of`; výchozí čas pozorování je dostupnost.
Skutečný čas měření má dodat karta. Povolené názvy jsou `CONTEXT_FLAGS`,
`OBSERVATION_FLAGS`, `OBSERVATION_NUMBERS` v `meddi/clinical_rules.py`, navíc
`pain_nrs`, `overall_feeling` a `pain_persists_after_rescue_dose`.
Neznámé klinické pole v explicitním kontextu/snapshotu je chyba vstupu.

Volitelný argument `context={...}` umožňuje dosavadní přímé volání bez karty.
Jeho léčebné příznaky jsou explicitní aktuální přepis snapshotu; číselná
pozorování se vybírají podle času společně s ostatními zdroji.

## Co se převádí

- Potvrzené odpovědi všech definovaných otázek: validace a příprava přes
  `meddi.form.prepare_checkin`. Text a možnosti se načítají z původních definic;
  text možností převzatý v paketu je nepřepisuje. Barvu počítá jádro pravidel.
- Přesné číselné fakty a explicitní logické příznaky: registry `NUMERIC_FACTS`
  a `FLAG_FACTS` v `meddi/pipeline.py`. Například `temperature` → `temperature_c`,
  `spo2` → `spo2_pct`, `pain.nrs` → `pain_nrs`, `confusion` → `confusion`.
- `vomiting.episodes` → `vomiting_episodes_24h` pouze při doložených 24 hodinách
  nebo odpovědi na původní cílenou otázku o zvracení. Počet stolic celkem není
  automaticky nárůst oproti normálu. `diarrhea.increase_over_baseline` potřebuje
  doložené 24hodinové okno. Kanonické názvy s `_24h` už toto okno deklarují.
- Negace logického příznaku → `false`; negace číselného měření nevytváří nulu.
  Příznaky pečujícího nejsou příznaky pacienta, s výjimkou samostatného pravidla
  `caregiver_exhaustion`, které skutečně hodnotí pečujícího.

Jiný koncept, interval, neurčený subjekt, nejistý nález nebo nevyřešený čas
zůstává v `unprocessed_facts` s důvodem a odkazem na zdroj. Samotné přiřazení
k tématu otázky není důkazem všech podmínek klinického pravidla. Původní fakt
ani jeho potvrzení se nepřepisují. Registr lze rozšiřovat až po domluvě přesného
významu a doptání, které chybějící rozlišení získá.

## Čas, rozpory a validace

Výchozí `now` je poslední dostupnost zprávy v paketu, nikoli systémové hodiny.
Pro přehrávání lze zadat explicitní `now` / CLI `--at`. Budoucí nebo expirované
záznamy se nezapočtou a zůstanou v `deferred_inputs`. Budoucí snapshot a jiný
pacient se odmítnou. Pozorování nemůže být známé dříve, než nastalo:
platí `observed_at <= available_at`. Všechny zadané časy vyžadují pásmo.

Pro stejný parametr se vybírá nejnovější známý čas pozorování. Při současném
rozporu se zachovají **všechny** hodnoty a jádro vybere nejvyšší doložené
pravidlo. Pouhé maximum čísla nestačí například u nízké a vysoké glykemie.
Novější normální hodnota tak může nahradit starší rizikovou hodnotu; nebere se
maximum z celé historie pacienta. Odpověď na rozsah teploty a přesné měření
sdílejí stejný parametr, obdobně odpověď/počet zvracení a průjmu.
Při neznámém čase se hodnoty zachovají a vznikne `unknown_observation_time`.

Doslovný `time_text` je ověřen proti původní zprávě. Zpracuje se jen malý
explicitní seznam současných/24hodinových vyjádření. „Od rána“ se nepřekládá
na 24 hodin; obecná normalizace relativního času ještě není implementovaná.
Bez zvláštního časového vyjádření se aktuální kontakt vztahuje k dostupnosti
zprávy. Automatická klinická expirace se nevymýšlí.

`meddi/validation.py` sdílí kontrolu domén a jednotek pro formuláře, připravený
check-in i nové vstupy. NaN, nekonečno, boolean místo čísla, neplatný rozsah
nebo jednotka se odmítnou před pravidly. `degC` je přijímaná jednotka.
Chybný vstup vyvolá `ValueError` nebo `TypeError`; nezmění se v negativní nález.

## Výstup pro další pipeline

Výstup je JSON `kind=meddi_contact_assessment`, `schema_version=1`:

| Pole | Význam |
| --- | --- |
| `minimum_color` | Maximum doložených a výslovně předběžných úrovní; green znamená jen neprokázanou eskalaci |
| `color` | Známá eskalace, nebo null při neúplném posouzení se zeleným minimem |
| `assessment_status`, `requires_review` | Complete/incomplete a potřeba dořešení; complete platí jen pro implementovaný rozsah |
| `scores`, `reasons` | Skóre, důvody, zdrojový oddíl pravidel a důkazy |
| `review_issues`, `skipped_rules` | Nevyhodnocené podmínky a konkrétní chybějící vstupy z jádra |
| `adapter_issues`, `unprocessed_facts`, `deferred_inputs` | Rozpory, nezařazené významy a časově vyřazené vstupy |
| `triage_inputs` | Přesné `prepared`, `context`, `observations` použité jádrem včetně odkazů na zdroje |
| `intake` | Hluboká kopie celého původního paketu: zprávy, fakta, odpovědi, potvrzení a stav dialogu |
| `evaluated_at` | Čas přehrávání s pásmem |
| `rules_version` | Verze politiky pravidel; aktuálně 2, umožňuje reportu přepočítat staré výsledky z původních vstupů |

`color=red` a `assessment_status=incomplete` se nevylučují. Chybějící vstupy
jiných pravidel neruší známé červené minimum. Null není zelená ani automaticky
červená. `skipped_rules` se nemají mechanicky proměnit v desítky otázek pacientovi.
Karta má zachovat kontakt a vyhodnocení zvlášť; `triage_inputs` jsou odvozené
vstupy, nikoli náhrada zdrojových zpráv a skutečných potvrzení.

Od bezpečnostní opravy 17. 10. (`rules_version=2`) se nepokrytá nezelená odpověď
uchová jako předběžná úroveň podle jejího zdrojového signálu, včetně ESAS.
Vyhodnocené klinické pravidlo má přednost před barvou možnosti (např. pocit 5
→ oranžová). Pokud pravidlo má doložené příznaky a chybí pouze léčebný/rizikový
kontext, zachovává vyšší možnou úroveň. To platí také pro horečku ≥38 °C bez
známé chemoterapie, NRS ≥7 bez známého účinku SOS a suicidální myšlenky bez
ověřeného plánu. Důvod má `provisional=true` a `uncertainty_source` s §6.4;
`skipped_rules` nadále eviduje chybějící podmínky. Nepotvrzené návrhy odpovědí,
budoucí/expirované údaje ani pouhá chybějící měření žádné minimum nevytvářejí.
Jde o konzervativní dočasnou politiku; ESAS gradient sám není klinické mapování.
Zdroj: pravidla §3, §6.4 a `dotazniky_definice.json`, ESAS / poznamka.

Web staré uložené výsledky přepočítává z uložených `triage_inputs`, bez změny
záznamu na disku a bez současných/budoucích údajů pacienta. Zachovává `intake`,
`evaluated_at`, problémy adaptéru a neúplnost původního posouzení.

## Lokální průchod bez API a tokenů

Z kořene repozitáře, stejně na Linuxu i v PowerShellu:

```text
uv run --locked python -m meddi.pipeline meddi/contact.example.json --snapshot meddi/snapshot.example.json --output assessment.json
```

Vstupy jsou ručně syntetické, vytvořené přes skutečný LLM kontrakt bez modelu.
Očekávaný výsledek je `minimum_color=red`, `color=red`, `assessment_status=incomplete`.
Starší normální teplota nepřekryje novou 38,2 °C; zvracení 6×/24 h projde také
před potvrzením. Výstup se nikam neposílá. Vlastní export MASTER lze vložit
místo `meddi/contact.example.json`, s odpovídajícím snapshotem nebo bez něj.
`--context context.json` přijme pouze normalizovaný kontext; `--at` nastaví čas.

Zpětná kompatibilita: `triage.evaluate_pipeline_packet()` a
`triage.evaluate_intake()` delegují do stejného adaptéru. Kořenové
`evaluate_triage()` zachovává starý plochý vstup a rozsah čtyř kritérií
(`scope=flat_four_criteria`), jejich funkce importuje z `meddi.triage`.
Nízká úroveň `meddi.triage.evaluate_checkin()` dál zachovává svou politiku
zeleného minima + review; konzervativní prezentaci dělá nová fasáda.

## Meze tohoto kroku

Zdroj: `rakathon_meddi_onco_data/docs/pravidla_triaze.md`, §3 a §6.2–6.4;
definice odpovědí: `rakathon_meddi_onco_data/docs/dotazniky_definice.json`.
Nejde o úplné klinické ověření protokolu. Předběžná politika výše pokrývá
nevyhodnocené signály odpovědí a neznámý kontext při doložených příznacích.
Obecné intervaly a alternativy s chybějícími příznaky stále pouze zachováváme
a označujeme jako neúplné. Časování, relevantnost chybějících podmínek, intervence týmu
a napojení vyhodnocení po každém tahu jsou úkolem nadřazené orchestrace.
Zůstávají rozpory zdroje NRS 0–10 vs. typ škály 1–10 a průjem >7 vs. ≥7;
zdrojový JSON ani LLM prompt se v tomto kroku neměnily. Backendové pravidlo
NRS přijímá 0–10, původní Intake nad typem škály nadále 1–10; sjednotit po
potvrzení významu zdroje týmem/mentorem. Kvalifikované klinické review zůstává nutné.
