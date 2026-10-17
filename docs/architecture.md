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
| `web/app.py` | Výběr profilu, MASTER, cílené doptání, společná kontrola, opravy a potvrzení | Přihlášení/role, volba zastupování, personalizace a bezpečnostní výstup během sběru |
| `web/patient_store.py` | Pracovní kopie pacienta a atomické přidání potvrzeného check-inu | Trvalé události před LLM, průběžné revize, obnovení kontaktu a podpora více procesů |
| `web/patient_report.py`, `meddi/status.py` | Poslední/historická triáž, historie odpovědí a měření, nezelené incidenty a grafy | Aktivní epizody, stručná aktuální kartička, plán kontrol a pracovní přehled lékaře |
| `notifications/` | Samostatný formulář pro pevný testovací e-mail a SMTP transport | Napojení na triáž, adresáti/priorita, spolehlivé předání a převzetí |
| `main.py` | Chronologicky omezené strukturované vstupy a oddělené porovnání s referencemi | Replay celého toku včetně zpráv, kontrol, intervencí a souhrnů |

Plánovač, nové strukturované měření/přeměření, producent odborného souhrnu
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

Živý web:

```text
MessageEvent → MasterDialogue.start/submit
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

## Web a ukládání

| Cesta | Význam |
| --- | --- |
| `/` | Výběr profilu a jeden MASTER kontakt |
| `/patients/<patient_id>/report` | Report profilu z pracovní kopie nebo původních dat |
| `/assets/plotly-<version>.min.js` | Lokálně poskytovaný Plotly skript |
| `/static/<path:filename>` | Styly a skripty webu |

Výběr profilu není autentizace. Výchozí MASTER zní „Jak se dnes cítíte?“.
Web používá `bulk_confirmation=True`: návrhy se kontrolují společně,
`revise(index)` otevře opravu a zneplatní závislé odpovědi, `confirm_all()`
potvrdí jen vyřešené návrhy. Fakta z obecné extrakce tím nejsou samostatně
potvrzená. Výchozí `MAX_QUESTIONS=6` omezuje počet položených otázek včetně MASTER.

Relace jsou ve slovníku v paměti procesu, klíčované browser session.
Restart formuláře zachová vybraný profil. Dokončený formulář další změny
odmítne; výslovný restart založí nový kontakt. Restart procesu rozpracované
relace neobnoví. `FLASK_SECRET_KEY` lze dodat prostředím; jinak vznikne náhodně
při startu, takže nejde o konfiguraci trvalého přihlášení.

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
- `web.app.index` při chybě extrakce vrací předchozí stav relace. Test
  `test_failed_extraction_preserves_current_state` chrání předchozí dialog,
  ne trvalé přijetí právě odeslané zprávy. Původní vstup se před LLM na disk
  neukládá a restart procesu relaci ztratí; řeší K2a/K2b.
- `assess_contact` z historického adaptéru předává pouze léčebný kontext,
  nikoli odvozené trendy v `observations`. Stará měření správně nepovažuje za
  dnešní; chybí ale doložené historické souvislosti pro živé hodnocení.
- `web.export.meddi_record` zapisuje prázdné `vitalni_funkce`, spojuje všechny
  zprávy do `zprava_pacienta` a nastavuje autora na pacienta. Vytěžené měření
  tak může ovlivnit triáž a zůstat v intake, ale nepřibude do grafu měření.
- Historie incidentů není registr aktivních klíčových/varovných nálezů.
  Označení „varovné“ v reportu zahrnuje i žluté historické údaje, a proto
  neodpovídá užšímu týmovému významu aktuálních varovných příznaků.
- `upozornit_tym` je požadovaná akce v datech. Neprokazuje odeslání ani převzetí.
  Chybí trvalá evidence příjemce, priority, termínu, pokusů a převzetí;
  samostatné SMTP demo ji nenahrazuje.
- `web.app` předává hodnocení a exportu časy přes `datetime.now().astimezone()`;
  ty závisejí na pásmu serveru. `disposition` zatím vrací obecný kontaktní
  text, nikoli termín vypočtený pro konkrétní okamžik. K3/K6 musí předávat
  explicitní čas a směrování počítat v `Europe/Prague`.

## Výchozí stav pro K2

Jednorázový výchozí bod auditu z 2026-10-17, revize `7a73ce3`;
po změně implementace tento stav nahradit nebo odstranit, nepřidávat historii běhů.

- `uv run --locked python -m pytest -q`: 654 testů prošlo.
- `uv run --locked ruff check .`: dvě ISC004 v `meddi/disposition.py`.
- `uv run --locked python main.py --comparison lower`: 86/171 shod,
  7 nižších a 78 vyšších výsledků; `requires_review` u všech 171 kontaktů.
  U jedné ze šesti referenčně červených situací vyšla oranžová.
- `tests/test_notifications.py` neexistuje; dříve uvedený příkaz v notifikačním
  README proto selhal bez spuštění testů. Pokrytí SMTP je otevřený úkol.

Replay výše používá pouze strukturovanou cestu, bez interpretace původních
zpráv. Vyšší výsledek není sám o sobě prokázaná zbytečná eskalace;
`requires_review` zahrnuje i chybějící podmínky hypotetických pravidel.
Rozdíly je nutné vysvětlit vstupy, extrakcí, mapováním, trendem či sporným
pravidlem. Prošlé testy ověřují i dosavadní skrývání červeného výsledku,
nikoli splnění P07. Výchozí bod není klinická validace ani ověření živého
LLM, SMTP, úplného produktu nebo Windows.

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
`--comparison` filtruje řádky, souhrn stále počítá celou sadu. Testy intake/webu
používají náhrady LLM; automatické testy SMTP zatím chybí. Živé evaluace jsou
samostatná explicitní volání se syntetickými daty.
Prošlé testy a správné schéma neprokazují klinickou správnost nebo úplnost
extrakce. Testovací výsledky průběžně získávat příkazy, nevést jejich historii
jako součást specifikace.
