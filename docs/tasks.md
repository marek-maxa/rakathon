# Otevřené úkoly MEDDI ONCO

Stavy: `todo`, `doing`, `blocked`, `done`. Jeden vlastník na úkol.
Hotovou implementaci popisuje [architektura](architecture.md), podmínky kroků
[plán](meddi-onco-plan.md#implementační-kroky-a-závislosti).
Dokončené provozní zápisy a historii testovacích běhů zde neudržujeme.

## Rozpracovaná práce

Tyto dvě práce zachovávají původní vlastnictví relace web; nepřebírat je
souběžným zápisem do stejného checkoutu.

| Úkol | Vlastník | Stav | Podmínka dokončení |
| --- | --- | --- | --- |
| Audit nadměrné eskalace a pokrytí, K7/K9; answer_coverage, triage, testy | Relace web | doing | Vysvětlit aktuální zvýšené výsledky a neúplnost; běžné/mírné odpovědi a větvení skutečně vyhodnotit. Neskrývat texty, neznámá měření či chybějící odpovědi kvůli více zeleným. Ověřit celou časovou sadu i syntetické proti-příklady bez referencí v rozhodování |
| Dokončit ověření konkrétního kroku pro každé hodnocení, část K6; disposition, pipeline, web a testy | Relace web | doing | Současná výstupní politika již existuje; ověřit všechny vstupní cesty a uložené výsledky. Úroveň 1–4, krok a kontakt, neúplnost zvlášť, známé 3/4 zachované; neaktivní hypotetická pravidla neeskalují rutinní kontakt |

## Navazující implementace

K1 má použitelný základ. Nejbližší integrační celek je K2, poté K3/K4;
rozpracované klinické ověřování nepovažovat za dokončené jen kvůli novému UI.

| Krok / rozsah | Vlastník | Stav | Zbývající práce |
| --- | --- | --- | --- |
| K2 · události, měření, úložné rozhraní a export | Tým | todo | Originál před LLM, stabilní ID, trvalé revize/obnovení, autor i opravy zachované, MASTER a cílené odpovědi oddělené, měření v historii/grafu/triáži a deduplikace |
| K3 · časový kontext a skutečné podání léčby | Tým | todo | Odlišit plán/podání/druh cyklu, poslední chemo se zdrojem a odstupem; potřebné trendy předat i živému webu bez budoucích dat |
| K4 · aplikační orchestrace a bezpečnostní výstup | Tým | todo | Vyřešit konflikt zobrazení, vyhodnotit známé riziko před dalším cíleným LLM, uložit konečné i přerušené revize; chyba neztratí podklady |
| K5 · epizody, otázky a přeměření | Tým | todo | Klíčové/varovné nálezy, zlepšení a uzavření, společný plán kontrol, odpověď/remeasurement, běh v čase, neodpověď a deduplikace; schválené intervaly |
| K6 · doporučení, kontakty, předání a souhrn | Tým | todo | Doplnit konkrétní nálezy/plány, vypočtené lhůty, předání/převzetí/opakování, pevnou předlohu souhrnu s LLM pouze pro formulaci a šablonovou zálohu |
| K7 · zprávy, nejistota a klinické mapování | Tým + mentor | todo | MASTER/importované zprávy stejnou cestou, konflikty/intervaly/nepokryté pojmy, schválené mapování škál; vyřešit O1–O10 backendu, neladit podle referenčních ID |
| K8 · pacientský a zdravotnický web | Tým | todo | Stručná kartička/detail/LLM stejné revize, kontroly, prioritní požadavky a zásahy týmu; role, volba zastupování a správné oslovení bez změny významu otázek |
| K9 · úplný replay a demo | Tým | todo | Všech 171 check-inů a šest povinných situací včetně negativních/mezních případů; záchyt i zbytečné eskalace, srozumitelnost a záložní demo bez LLM |
| K10 · MEDDI a provoz v EU | Tým + pracoviště | todo | Integrační/provozní kontrakt, data a model v EU, přístupy, obnova, doručení, odpovědnosti a klinické převzetí; skutečné nasazení zvlášť |
| Lint · `meddi/disposition.py` | Tým | todo | Vyřešit dvě stávající ISC004 u spojovaných textů doporučení beze změny obsahu a ověřit Ruff |

## Rozhodnutí potřebná před dokončením

- K4: výslovně dořešit [konflikt okamžité kritické instrukce](decisions.md#otevřený-konflikt-bezpečnostního-výstupu)
  se skrýváním triáže až do potvrzení.
- K3/K5–K7: kvalifikovaně potvrdit [klinické a časové otázky O1–O10](backend.md#otevřené-klinické-otázky),
  zejména škály, rozpory definic, poslední podání, intervaly přeměření a dostupnost dat.
- K9/K10: s pořadateli ověřit formát/termín odevzdání a hodnoticí rozhraní;
  s pracovištěm kontakty, kalendář, cílové prostředí a odpovědnost za převzetí.

Kontroly a spouštěcí příkazy jsou v [architektuře](architecture.md#spuštění-a-kontroly).
Při změně úkolu aktualizovat jeho stav a odpovídající rozhraní/rozhodnutí,
nepřidávat nový historický audit se stejnými požadavky.
