# Porovnání a sloučení 16. 10. 2026

Výchozí commit `27d6093`, vzdálený `d1b58f4` (Implement structured check-in
triage rules and treatment context), lokálně sedm změněných souborů.
Pull proběhl fast-forward; obnovení lokálních změn vyvolalo konflikty pouze
v `docs/tasks.md` a `docs/decisions.md`. Kód neměl textový konflikt.

## Rozhodnutí a důkazy

| Rozhodnutí | Důvod a opora |
| --- | --- |
| Přijmout nové `meddi/` a jeho testy beze změny | Vzdálený commit rozšiřuje strukturovaná pravidla, důvody a časově filtrovaný kontext. `main.compare_patient` předává do pravidel jen připravené vstupy, reference používá až pro porovnání. Lokální změny tyto soubory neupravují. |
| Obnovit historii LLM v úkolech a rozhodnutích | `git diff 27d6093 d1b58f4 -- docs/tasks.md docs/decisions.md` obsahuje pouze odstranění těchto zápisů, bez náhrady. Kód a testy MASTER dialogu přitom zůstávají. Smazání zápisů by zkreslilo skutečný stav a důvody existující implementace. |
| Zachovat lokální veřejné exporty s odloženým importem | `MasterDialogue`, `load_topic_catalog` a `resolve_topics` existují, test kořenového API ověřuje jejich dostupnost. Odložený import zachovává `python -m llm_intake.dialogue` a `master` bez varování. |
| Zachovat lokální pipeline adaptér jako omezený prototyp | `triage.evaluate_pipeline_packet` přijímá `question_answers` a `facts`; `meddi.triage.evaluate_checkin` vyžaduje `prepare_checkin` s `answers`, vitálními funkcemi a oddělenými pozorováními. Přímá záměna funkcí by porušila kontrakt a ztratila vstupy. |
| Nesjednocovat automaticky politiku neúplných dat | Syntetický vstup `overall_feeling=1` vrací v kořenovém prototypu `color=null`, v `meddi.triage.evaluate_triage` `green`; obě cesty mají `requires_review=true`. Nové jádro navíc vrací `skipped_rules`. Toto je rozdíl chování, nikoli konflikt textu. |
| Opravit široké mapování teploty v lokálním adaptéru | Před opravou se `temperature.duration=40 hours` při kontextu chemoterapie přeložilo na 40 °C a červenou. Nyní se mapují jen přesné pojmy `temperature`, `oxygen`, `spo2`, kontroluje se konečné číslo, deklarovaná jednotka a doména. Osm regresních případů pokrývá záměnu délky, boolean, NaN, nekonečno, jednotky a rozsahy. Klinické prahy se nemění. |

## Hranice a otevřené otázky

- Přeskakování neznámých údajů je v dokumentaci vzdáleného commitu označené
  za vývojovou výjimku z `pravidla_triaze.md`, §6.4. Sloučení ji zachovává
  v `meddi/`, ale neprohlašuje ji za klinicky potvrzenou politiku. Neslučujeme
  ji potichu s dřívějším návrhem konzervativního posouzení v MASTER.
- Pipeline adaptér sám neověřuje časovou dostupnost, stáří měření, nejistotu,
  citace a konflikty faktů. Bere první vhodné měření přes `setdefault`, kontext
  má přednost; nepřenáší původ do důvodů. Volající proto musí připravit již
  vybrané aktuální hodnoty. Jednotka `null` je pro zpětnou kompatibilitu
  přijímána jako předem normalizovaná hodnota, nikoli převáděna odhadem.
- Interval se nepřekládá na přesné měření. Neznámý pojem se zde nevyhodnotí;
  uchování a posouzení těchto zjištění zůstává úkolem celé pipeline.
- Propojení LLM paketu s širším jádrem potřebuje samostatný domluvený adaptér
  se zdroji, časem, jednotkami a politikou konfliktů. `MasterDialogue` zatím
  žádnou triáž automaticky nespouští.
- Mapování léků a klinické interpretace z nového jádra nebyly při tomto
  sloučení nově ověřovány; jejich zdroje a omezení jsou v architecture.md.

## Provedené ověření

Před pullem 262 testů; po sloučení 494; po opravě mapování 502 testů prošlo
(`uv run --locked python -m pytest -q`). Ruff check prošel. Čísla zahrnují
odlišné sady, nejde o zlepšení přesnosti modelu nebo klinickou validaci.
Dále prošly CLI `--help` pro master/dialogue s varováními jako chybami,
CLI main, dostupnost nových kořenových exportů, formát obou upravených
Python souborů, 15 místních odkazů a kontrola konfliktových značek.
Kontroly proběhly na Linuxu, bez živého volání LLM a bez spuštění Windows.
