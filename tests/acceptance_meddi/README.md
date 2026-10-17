# Přijímací testy MEDDI pro navazujícího agenta

Připraveno je **502 syntetických scénářů pro 140 zdrojových požadavků**:
443 automaticky hodnotitelných, 28 s otevřeným klinickým rozhodnutím
a 31 pro lidské posouzení textu či rozhraní. Očekávání vznikla přepisem
zdrojů, bez čtení `ground_truth` a bez odvozování výsledků z implementace.
Sada je připravená k napojení; **splnění aplikací zatím nebylo ověřeno**.

Konečná sada nemůže vyjmenovat všechny možné pacientské věty. Pokrývá
všechny řádky červených/oranžových pravidel, všechny odrážky žlutých
situací, kontexty a obecná pravidla; přidává hranice, negace, jazykové
varianty, rozpory, časový vývoj a integrační selhání. Pokrytí znamená
existenci přijímacího případu, nikoli klinickou validaci systému.

## Soubory a zdroje

| Soubor | Účel |
| --- | --- |
| [catalogue.md](catalogue.md) | Čitelný seznam každého případu, očekávané minimum a přesný zdroj; doplňující kontroly jsou v JSON |
| [inputs.jsonl](inputs.jsonl) | Samostatné vstupy: zprávy, autor, kontext, časy, případně odpovědi a měření |
| [expectations.jsonl](expectations.jsonl) | Oddělená očekávání, kontrolní podmínky, nejistoty a zdroje |
| [requirements.json](requirements.json) | Registr 140 požadavků, jejich význam a původ |
| [coverage.json](coverage.json) | Mapa část zdroje → požadavky → scénáře |
| [sources.json](sources.json) | Původní soubory a jejich SHA-256; PDF má 13 stran, PPTX 6 slidů |
| [build_suite.py](build_suite.py) | Autorský předpis scénářů; negeneruje očekávání z aplikace |
| [run.py](run.py) | Kontrola sady, výpis a vyhodnocení samostatně dodaného adaptéru |

Klinická minima a kontakty vycházejí z
[pravidel triáže](../../rakathon_meddi_onco_data/docs/pravidla_triaze.md),
§1–6. Soutěžní scénáře a hodnocení vycházejí z
[MEDDI – MEDDI Onco.pdf](<../../documents/MEDDI – MEDDI Onco.pdf>), s. 7–12.
Požadavky na koordinaci, prioritu a další krok jsou navíc v
[prezentaci PPTX](../../documents/MEDDI_Onco_Rakathon_2026.pptx), slidy 2–3 a 5.
Bezpečnost a použití dat doplňuje
[README balíčku](../../rakathon_meddi_onco_data/README.md), §6.
Dotazníkové možnosti ověřuje
[definice dotazníků](../../rakathon_meddi_onco_data/docs/dotazniky_definice.json).
Každý jednotlivý případ obsahuje konkrétní odkaz včetně §/strany/slidu.

## Šest situací, se kterými začít

Všechny jsou výslovně požadované v PDF, **s. 9**. Tag `required-six`
vybírá 58 scénářů: hlavní případy, negativní protějšky, jazykové varianty
a relevantní časový vývoj.

| Rodina ID | Co zachytit | Klinický zdroj |
| --- | --- | --- |
| `PRESENTATION-FEVER` | Horečka v nadiru po chemoterapii | Pravidla §3 / Červená / Horečka; §5 / Den 7–14 |
| `PRESENTATION-COLITIS` | Zhoršování průjmu na imunoterapii během dvou dnů; replay 2 → 3 → 4 bez znalosti budoucnosti | §3 / Průjem a Průjem na imunoterapii; §6.1 |
| `PRESENTATION-HEART` | Přírůstek hmotnosti, pokles saturace, ortopnoe a dušnost v klidu | §3 / Dýchání; §4 / Hmotnost; §6.1 |
| `PRESENTATION-INTERACTION` | Warfarin + kapecitabin a krvácení; interakce sama není krvácení | §3 / Krvácení; §5 / Antikoagulace |
| `PRESENTATION-PALLIATIVE` | Za pacientku píše dcera; přání nesmí zablokovat pomoc a potíže patří správné osobě | §3 / Opioidy; §5 / Paliativní péče; §6.7 |
| `PRESENTATION-CONFLICT` | Závažná zpráva navzdory klidné odpovědi v dotazníku; doptat a zatím zachovat horší variantu | §6.2–4 |

Názvy kolitida/srdeční selhání označují rodinu přijímacího scénáře.
Pacientovi nesmí systém potvrzovat diagnózu ani měnit léčbu
(pravidla §6.5; PDF s. 7).

## Spuštění kontroly a výběru případů

Z kořene repozitáře; Python 3.12 a uv, stejné příkazy v PowerShellu i Linuxu:

```text
uv run --locked python -X utf8 tests/acceptance_meddi/run.py validate
uv run --locked python -X utf8 tests/acceptance_meddi/run.py self-check
uv run --locked python -X utf8 tests/acceptance_meddi/run.py list --tag required-six
uv run --locked python -X utf8 tests/acceptance_meddi/run.py list --tag boundary
uv run --locked python -X utf8 tests/acceptance_meddi/run.py list --grading clinical_review
```

`validate` kontroluje identifikátory, vazby, zdroje a jejich hash, časové
údaje, podporované kontroly a pokrytí tabulek tvrdých pravidel.
`self-check` zkouší samotný hodnoticí nástroj na záměrně podhodnoceném
i nadhodnoceném výsledku, lidském review a úniku budoucí události.
Tyto příkazy **nespouštějí aplikaci ani LLM**.

Soubory záměrně nejsou `test_*.py`: běžný pytest zatím tuto nesplněnou
přijímací sadu nesmí prezentovat jako hotové regresní testy aplikace.
Po skutečné změně zdrojů nejprve zkontrolovat její dopad na očekávání;
teprve potom regenerovat přes `build_suite.py`. Samotné přepsání hashe
není přezkoumání zdroje. Ruční změny generovaných JSONů/katalogu přepíše
generátor; opravovat autorský předpis a zdokumentovat důvod.

## Úkol pro dalšího agenta

1. Přečíst zdroje a případy; zachovat očekávání nezávislá na implementaci.
2. Přidat tenký adaptér skutečného backendu a webového toku. Nepřepisovat
   kliniku do druhého testovacího jádra a nevracet výsledek podle ID případu.
3. Spustit nejprve šest prioritních rodin, potom zprávy, strukturované
   vstupy, hranice, směrování a celý průchod; opravovat aplikaci.
4. Oddělit běhy se skutečným LLM od běhů s náhradou extrakce. Náhrada,
   která vrací očekávaná fakta, neověřuje porozumění pacientské zprávě.
5. Uložit skutečné výsledky s konfigurací běhu do `.scratch/`; klinické
   nejasnosti předat mentorovi. Změnu očekávání připustit jen s doloženým
   zdrojem nebo výslovným klinickým rozhodnutím, nikoli kvůli zelenému běhu.

Adaptér `module:function` přijímá jediný slovník vstupu a vrací slovník
pozorovaného výsledku. Modul musí být importovatelný z kořene repozitáře.
Příklad příkazu **až po implementaci takového adaptéru**:

```text
uv run --locked python -X utf8 tests/acceptance_meddi/run.py evaluate --adapter acceptance_adapter:evaluate --tag required-six --report .scratch/acceptance-six.json
uv run --locked python -X utf8 tests/acceptance_meddi/run.py evaluate --adapter acceptance_adapter:evaluate --report .scratch/acceptance-all.json
```

Výchozí běh blokuje standardní Python síťový socket, SMTP a SMTP_SSL,
včetně importu adaptéru. `--allow-network` je výslovná volba pro schválený
běh skutečného LLM; SMTP zůstává blokované. Jde o ochranu běžných transportů,
nikoli izolaci nedůvěryhodného kódu. Adaptér musí respektovat
`test_environment.no_external_send`: nesmí posílat e-maily, klinická
předání ani nasazovat aplikaci. Testovací profily a pracovní úložiště
musí mít oddělené od běžného dema.

## Kontrakt vstupu a výsledku

Spouštěč předává pouze obsah `inputs.jsonl` **bez ID případu**; očekávání,
zdroje ani popisy požadavků adaptér nedostává. Pro LLM/rozhodování nečíst
`expectations.jsonl`, `requirements.json`, katalog, zdrojové názvy scénářů
ani `ground_truth`. Oddělení reference vyžadují PDF s. 10 a README §4–5.

| Vstup | Význam |
| --- | --- |
| `assessment_at` | Čas hodnocení s offsetem; směrování používá Europe/Prague |
| `patient`, `patient_context` | Syntetická identita a dostupný léčebný/výchozí kontext; nepřítomný údaj není automaticky `false` |
| `events`, `history` | Doslovné zprávy/události s `id`, `available_at`, případně `observed_at`, autorem a zdrojem; budoucí filtrovat **před** LLM |
| `questionnaire_answers` | Odpovědi identifikované dotazníkem/otázkou; indexy možností jsou od nuly podle definic |
| `structured_observations` | Strukturovaný protějšek pro izolované ověření pravidel; nevyžaduje jazykovou extrakci |
| `entrypoint: routing`, `known_assessment` | Izolovaný test směrování již známé úrovně; toto není reference pro extrakci zprávy |
| `test_environment.failure_to_inject` | Řízená chyba transportu/zápisu či opakování; adaptér ji musí skutečně vyvolat, ne jen deklarovat |

Minimální výstup vždy obsahuje `level` (celé číslo 1–4), `next_step`
a `team_notification_required`. Kódy kroku odpovídají pravidlům §1.
Další pole musí být skutečně odvozená z provedeného toku, nikoli opsaná
z očekávání. Názvy níže jsou společný hodnoticí kontrakt; převod názvů
existujícího backendu patří do adaptéru.

| Výstup | Kontrola |
| --- | --- |
| `observations` | Slovník nálezů; požadované kanonické názvy uvádí `observations_subset` v očekáváních |
| `evidence` | Seznam `{event_id, quote}` s doslovnou citací nebo `{input_path}` jako `/structured_observations/temperature_c`; budoucí událost není přípustná |
| `used_event_ids`, `llm_requests` | Skutečně použité události a zachycené požadavky modelu; časové případy obě pole vyžadují, bez LLM je seznam požadavků prázdný |
| `follow_up_questions`, `conflicts` | Skutečné doplňující otázky a zaznamenané rozpory; nesmí oddálit naléhavou instrukci |
| `needs_review`, `reminder_required` | Samostatná neúplnost/nejistota a připomenutí, pokud jsou v daném případě předepsané |
| `trace` | Pozorované pořadí událostí s `kind`: `urgent_instruction`, `targeted_llm`, `confirm`; nevyrábět pořadí dodatečně podle výsledku |
| `patient_text` | Skutečný text instrukce; lidská kontrola ověřuje srozumitelnost, oslovení a zákaz diagnóz/dávek |
| `routing` | `phone`, `within_working_hours`, `response_due_at`, `team_notify_by`, `before_next_dose`, `contact_code`; termíny s offsetem |

Podrobnosti podporovaných kontrol jsou v `run.py`; všechny kontroly
konkrétního případu jsou ve vedlejším záznamu `expectations.jsonl`.
`must_not_infer` znamená, že chybějící/nepřesný údaj nesmí být vydán za
přesné číslo. Rozmezí lze uchovat samostatně, nikoli smyšleným bodem
v poli určeném pro přesné měření. Budoucí údaje se filtrují podle
`available_at`, nikoli jen podle času jejich klinického výskytu.

## Jak číst výsledek a nejasnosti

- `level_min` je nejnižší přípustná úroveň. Tvrdá pravidla připouštějí
  vyšší úroveň; nevyžadují vždy přesnou shodu (pravidla, úvod a §3).
- `level_max` je předepsané maximum jen u výslovných kalibračních případů
  nebo izolovaného směrování. Samotné nedosažení jednoho prahu neznamená
  zelenou. Negace ale nesmí vytvořit popřený příznak nebo nepodloženou
  naléhavou instrukci (PDF s. 10; pravidla §6.2–4).
- `automatic`: zadané podmínky umí ověřit spouštěč. To nepředstavuje
  nezávislé klinické schválení přepisu pravidel ani celé aplikace.
- `clinical_review`: zdroj neurčuje úplnou odpověď nebo obsahuje rozpor;
  zůstává `REVIEW_REQUIRED`, dokud rozhodnutí nepotvrdí kvalifikovaný člověk.
- `human_review`: vyžaduje kontrolu textu, oslovení, rozhraní, souhrnu
  čitelného do 30 sekund či provozních vlastností (PDF s. 7 a 12).
- I u review případů se vynucuje doložené číselné minimum a další strojové
  podmínky. Nesplnění vrací `FAIL`, review se nikdy samo nepovažuje za `PASS`.

Otevřené body zahrnují logiku párových tlakových prahů (AND/OR není
výslovně určeno), zařazení přesně 7:00/15:30, svátky a výjimky kalendáře,
převod ESAS/psychických škál na CTCAE, definici bolesti 0 versus škálu
1–10, intervalové odpovědi a čas nejistého posledního podání chemo.
Klinické rozhodnutí se nevymýšlí; do vyjasnění platí zdrojové pravidlo
doptání a vyšší možné úrovně (§6.4). Konkrétní poznámku obsahuje každý
takový případ. Neuvedené měření samo není důkaz akutního příznaku.

Výstupní report uvádí zdrojové soubory/hash, konfiguraci a stav každého
případu. Neobsahuje klíče ani obsah zachycených LLM požadavků. K lidskému
posouzení je nutné zachovat odpovídající syntetický výstup/UI v místním
artefaktu adaptéru. Návratové kódy: `0` všechny vybrané případy automaticky
prošly, `1` alespoň jedna chyba, `2` chyba CLI, `3` zbývá lidské review.
