# Připravenost LLM, triáže a karty na propojení

Aktualizace 17. 10. 2026: níže je zachovaná **historická revize** před opravami.
Nový [společný backend](backend.md) již sjednocuje LLM adaptér nad `meddi/`,
přijímá degC, vybírá aktuální pozorování podle času, zachovává současné konflikty,
odmítá NaN/nekonečno a opravuje negaci dlouhodobé bolesti. Rozlišuje minimum
a neúplnost a zachovává celý kontakt. Web a karta zůstávají mimo rozsah;
jejich závady se tímto neopravovaly. Otevřené zůstává klinické ověření,
obecné intervaly/relativní čas a rozpory definic. Nové kontroly a výsledky
jsou v [tasks.md](tasks.md).

Revize 16. 10. 2026, `main` na `0420073`, vzdálený `web` na `6aeb385`.
`git fetch origin web` potvrdil dostupnou verzi; větev se nepřepínala ani
neslučovala. Rozpracované nepushnuté změny kolegů nejsou součástí této kontroly.

**Lze začít integrační CLI prototyp. Celá pipeline zatím není hotová a samotnou
vrácenou barvu nelze vydávat za úplné posouzení pacienta.** LLM má použitelný
kontrakt, širší jádro triáže existuje, ale chybí mezi nimi společný adaptér.
Aktuální vzdálený web navíc očekává neexistující API dialogu.

## Skutečné moduly a jejich hranice

| Část | Co už umí | Co brání finálnímu propojení |
| --- | --- | --- |
| `llm_intake.MasterDialogue` | MASTER → fakta a témata všech 49 otázek → cílené doptání → potvrzení/oprava → JSON; zdroje, autor, nejistota, limit kontaktu | Triáž se automaticky nespouští. Relace žije v paměti; snapshot není implementované resume. Relativní čas faktu ještě není normalizovaný čas měření. |
| `triage.evaluate_pipeline_packet` | Přijme LLM paket, mapuje potvrzený pocit/NRS a některá měření | Používá staré čtyři podmínky. Nepředává zvracení, krvácení, zmatenost a další fakta širšímu jádru. Nespravuje čas/konflikty. |
| `meddi.triage.evaluate_checkin` | Širší strukturovaná pravidla, maximum prokázaných úrovní, důvody, důkazy, přesné chybějící vstupy | Očekává `prepared`, `context`, `observations`, nikoli LLM paket. Neinterpretuje zprávy a neřeší časování kontaktů ani kartu. |
| `meddi.patient_inputs.build_triage_inputs` | Připraví organizační check-in, omezený kontext léčby a některé číselné změny v dostupné historii | Není to pacientská karta ani univerzální lékový číselník. Nezpracovává zprávy, intervence týmu nebo obecné klinické trendy. |
| `origin/web` | Flask formulář a export potvrzených odpovědí do organizačního formátu | Chybí jeho očekávané API, export není úplný záznam kontaktu, identita pacienta je nyní identitou webové relace. Časovou kartu v pushnuté verzi nevidíme. |

## Zjištění před propojením

### 1. Dvě cesty triáže a nesouhlasící kontrakty

`llm_intake/__main__.py:7,66` volá kořenový `triage.evaluate_intake`.
Kořenový `triage.py:110` přijímá paket, ale mapuje jen pocit, NRS, teplotu
a saturaci. `main.py:38` používá jiné, výrazně širší jádro
`meddi.triage.evaluate_checkin` (`meddi/triage.py:130`).

Pro společnou pipeline doporučujeme jádro `meddi/`; oba vstupní formáty má
překládat jeden adaptér. Další klinické podmínky nekopírovat do kořenového
prototypu ani do webu. Toto je doporučení revize, nikoli provedené sjednocení.

Přejmenování polí samo nestačí. LLM má otevřené `concept`, hodnotu a doslovný
`time_text`; jádro má pevná pozorování jako `vomiting_episodes_24h`,
`stools_above_baseline_24h` nebo `new_marked_drowsiness`. Slovní ospalost
neprokazuje automaticky novost a nápadnost; počet epizod neprokazuje 24 hodin.
Pro první průchod mapovat jen přesně doložené významy. Pro širší pokrytí
domluvit slovník pozorování a doptání na potřebná rozlišení; neodvozovat barvu
modelem ani z podobnosti názvu otázky.

### 2. Nesoulad jednotky a pořadím závislý výběr měření

- `llm_intake/master_prompt.md:48` požaduje `degC`, ale
  `triage.py:132` tuto jednotku nepřijímá. Syntetický platný fakt
  `temperature=38.2, unit=degC` skončil `ValueError` místo vyhodnocení.
- `triage.py:147` vybírá přes `setdefault`. S kontextem chemoterapie vrátí
  dva fakty teploty v pořadí `[36.5, 39]` barvu null, v opačném pořadí red.
  Kontextové pole může navíc přebít nově sdělenou hodnotu. Adaptér neřeší
  stáří, časový rozsah ani rozdílné zdroje.

Před kartou potřebujeme společné jednotky, výběr aktuální epizody a explicitní
rozpor. Nesmí se mechanicky vzít maximum ze všech historických hodnot: nový
stav po intervenci nesmí trvale nést starou červenou. Zdroj požadavku:
`pravidla_triaze.md`, §6.2–6.4.

### 3. Konkrétní chyba v pravidlech bolesti na hrudi

`meddi/clinical_rules.py:280` pro `bol_hrud` ukládá `chest_pain = (index == 1)`.
Index 0 ale znamená **dlouhodobou léčenou bolest**, ne její nepřítomnost
(`dotazniky_definice.json`, `nezadouci_ucinky/bol_hrud`).

Reprodukce: tato odpověď + explicitní `high_blood_pressure=True`, ostatní
varovné příznaky false → green; přidání `chest_pain=True` → red. V kombinovaném
pravidle vysokého tlaku s varovnými příznaky se tak ztratí doložená bolest.
Zdroj: `pravidla_triaze.md`, §3 / Červená / Tlak.

Před integrací opravit rozlišení „bolest přítomna“ a „nová bolest“ a přidat
regresní test. Tato revize klinický kód neopravovala.

### 4. Neúplná validace hranice nového jádra

`meddi.form` ověřuje indexy a ESAS, část pozorování má kontrolu typů a
konečnosti. Nejde ale o jednotnou vstupní validaci. Syntetická teplota
`NaN` ve `vital_signs.teplota_c.hodnota` prošla přes `prepare_checkin` a
`evaluate_checkin` jako green s review: porovnání `NaN >= 38` je false.
Zdroj místa: `meddi/triage.py`, zpracování teploty v `vital_signs`.

Po spojení s novými zdroji dat ověřovat typ, konečnost, jednotku a přípustnou
doménu před pravidly; chybné měření nesmí být negativním nálezem.

### 5. Barva a neúplné posouzení jsou odlišné informace

`meddi/triage.py:139,434` záměrně přeskakuje neznámé podmínky podle dřívějšího
vývojového pokynu a bere maximum známých skóre. Výstup může být green i při
nevyhodnocené horečce nebo zprávě pacienta; `requires_review` to označuje.
Nejde o nově objevenou regresi proti této vývojové politice. Není to ovšem
plné splnění §6.4 protokolu a nelze zobrazit samotnou zelenou jako dokončenou
triáž. Na aktuálních datech má review **171/171** případů, zpravidla i desítky
`skipped_rules`; příznak sám tedy neurčuje užitečnou prioritu práce.

Navržené rozhraní oddělí prokázané minimum, stav úplnosti a konkrétní
chybějící rozlišení relevantní pro daný případ. Z chybějících všech ostatních
příznaků nelze automaticky udělat červenou ani celý seznam otázek pro pacienta.
Práce s podloženými alternativami, intervaly a nejasností vyžaduje společnou
politiku podle §6.4; LLM nesmí „horší“ možnost vydávat za potvrzenou zkušenost.

### 6. Web není kompatibilní s aktuálním dialogem

Pushnutý `web/app.py` (`6aeb385`) importuje `llm_intake.dialogue`, ale soubor
v této větvi **není**. Společný předek s main je `7b6e26f`. Samotné doplnění
souboru nestačí: web používá `bulk_confirmation=True`, `review_sessions`,
`confirm_all()` a `revise()`, které nynější `main` nemá. Ověřeno signaturou
a dostupností členů, bez spuštění Flask serveru. Změna `Intake.confirm(value)`
ve webové větvi tento rozdíl neřeší.

Před sloučením domluvit jednotlivé nebo souhrnné potvrzování a skutečné API.
Přidat smoke test vytvoření kontaktu, odpovědi, opravy, potvrzení a uložení;
teprve potom slučovat. Flask/python-dotenv jsou zatím jen ve webové větvi.

### 7. Webový export nesmí být jediným zdrojem karty

`web/export.py:75` ukládá dotazníky, ale ne `facts`, citace, stavy dialogu,
časový původ tahů nebo `pending_topic_ids`. Texty všech odpovědí spojí do jedné
`zprava_pacienta`, vitální funkce vyprázdní a status nastaví vždy `vyplneno`.
Autor je vždy pacient, časy jsou čas dokončení; pacientské ID pochází ze session.

Syntetická reprodukce se zprávou „Jsem zmatený“: MASTER uchoval fakt
`confusion` a stav unresolved. Export fakta vypustil, přesto uvedl vyplneno.
Po předání tohoto exportu do připravené triáže nebyla prokázána červená;
stejná triáž s explicitním `observations.confusion=True` vrátila red
(zdroj pravidla: §3 / Červená / Neurologie). Nedochází tedy ke ztrátě pravidla,
ale ke ztrátě strukturovaného vstupu. Zdrojový text zůstává, někdo by ho musel
znovu analyzovat. To je zbytečné a může přinést jinou extrakci.

Primárně uchovávat původní události a celý LLM paket; organizační JSON je
odvozený export. Karta potřebuje stabilní `patient_id` nezávislé na webové
session, historii a oddělené nevyřešené či nepotvrzené údaje. Varování z možností
dotazníku (`web/app.py:70`) nejsou výstupem kontextové triáže.

### 8. Známé rozpory definic nezmizely

- `bolest_analgeticka_terapie/nrs`: text uvádí 0–10, typ `skala_1_10`
  omezuje potvrzený intake na 1–10 (`llm_intake/core.py`, schéma a validátor).
  MASTER umí nulu uchovat, ale cílená potvrzená odpověď nula zatím neprojde.
- `nezadouci_ucinky/prujem`: možnost uvádí více než 7 nad normál, tvrdé
  pravidlo už alespoň 7 (§3 / Průjem). Přesně sdělených 7 proto předat jako
  samostatné číselné pozorování, ne měnit pacientovu odpověď.

Jde o rozpory organizačních podkladů, ne důvod automaticky měnit zdrojový JSON.
Interpretaci a pacientské potvrzování musí tým dořešit s mentorem; prozatím
hodnotu uchovat a nejistotu výslovně označit.

## Výsledky skutečného ověření

`uv run --locked python -m pytest -q`: **502 testů prošlo**. Ruff check prošel.
Bez nového placeného LLM volání a bez klinické validace mentorem.

Lokální přehrání přes `main.compare_patients` / `build_triage_inputs` na všech
14 fiktivních pacientech, reference načtené až pro porovnání:

| Výsledek | Počet |
| --- | ---: |
| Shoda úrovně | 132/171 (77,2 %) |
| Nižší než reference | 30 |
| Vyšší než reference | 9 |
| Review | 171 |
| Referenční červená: stejná / nižší | 4 / 2 |

Referenčních zelených je 115, žlutých 37, oranžových 13 a červených 6.
Z 30 nižších výsledků jde o 22 yellow→green, 3 orange→green,
3 orange→yellow a 2 red→orange. Devět vyšších výsledků je green→yellow.
77,2 % je shoda nynější **strukturované části**, nikoli přesnost celého řešení.
Zprávy nejsou překládány do `observations`; klinický úsudek a zásahy týmu
nemají být dovozovány z reference. Připojení LLM samo nezaručí odstranění
všech rozdílů.

Červené podhodnocené případy: `ONC-011-C09` (reference popisuje dehydrataci
a riziko ledvinného selhání) a `ONC-014-C09` (reference popisuje možnou opioidní
toxicitu; ve zprávě je nereagování a pomalé dýchání). Jde o popis organizační
reference, ne naše nově stanovené diagnózy. U druhého případu příslušné pravidlo
v jádru existuje, ale chybí strukturovaná pozorování ze zprávy.

Lokální podrobný report: `.scratch/pipeline-readiness-reference.json`.
Jednotlivé výstupy lze znovu prohlédnout bez sítě:

```text
uv run --locked python main.py
uv run --locked python main.py --comparison lower --details
uv run --locked python -m pytest -q
uv run --locked ruff check .
```

## Nejmenší doporučený integrační krok

1. Opravit doložené chyby převodu jednotek, významu bolesti a validace teploty.
2. Domluvit jedinou fasádu, např. `evaluate_contact(packet, patient_snapshot, now)`.
   Přeloží potvrzené odpovědi a přímo sdělené fakty na `prepared`, `context`,
   `observations` pro `meddi.triage.evaluate_checkin`; zachová zdroje, subjekt,
   jednotky, nejistotu a příslušnou epizodu. Počty za jiné období se nezmění
   na počet za 24 h a interval se nezmění na přesnou hodnotu.
   Časově neoznačené datum/čas organizačního check-inu a `available_at` s pásmem
   z LLM sjednotit explicitní časovou politikou; kartu nepřidávat jako přepis
   dnešních měření bez jejich původu a stáří.
3. První CLI scénář: MASTER → zvracení za výslovných 24 h → příslušná otázka
   a potvrzení → triáž → záznam do úložiště karty → opětovné načtení. Dále
   horečka s jednotkou degC a známým kontextem léčby. Žádný nový framework.
4. Při každé nové zprávě vyhodnotit již doložené varovné informace průběžně;
   nečekat se známým urgentním nálezem na dokončení všech otázek. Potvrzení
   odpovědí a prozatímní vyhodnocení jsou dvě různé věci (protokol §3, §6.4).
5. Na této fasádě sjednotit webové API. Kartu napojit na stejný výstup;
   nemá sama přepočítávat klinická pravidla. Pak přidat plánované kontroly
   sledovaných parametrů; intervaly musí mít domluvenou politiku.

Dokončení první integrace ověří skutečný průchod a načtení historie, větev
bez potvrzení, chybu LLM, vyčerpání rozpočtu, rozpor nové zprávy proti kartě
a příznak mimo definované otázky. Pro replay zůstávají ground truth a
budoucí události mimo vstup rozhodování.
