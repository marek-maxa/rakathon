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

Prioritou je MVP podle [omezeného rozsahu M1–M5](meddi-onco-plan.md#aktuální-rozsah-mvp).
K1 a K2a existují; na K2a nyní nenavazovat obnovou dialogu K2b.
M1 je hotové; nejbližší funkční rozšíření je M2, měření a potřebné trendy.

| Pořadí MVP | Vlastník | Stav | Podmínka dokončení |
| --- | --- | --- | --- |
| M1 · kartička a přehled požadavků | Relace Codex | done | Kartička v reportu a `/team`, důvod/krok/kontakt/čas/zdroj stejného posledního hodnocení; šablonový souhrn a označená simulace předání. Přehled řadí požadavky podle výsledné úrovně; neúplnost zobrazuje zvlášť |
| UI · vstup Pacient / Lékař | Relace Codex | done | Úvodní volba na `/`, rozhovor na `/patient`, lékařský přehled na `/team`; přepnutí v demo patičce zachová rozhovor. Výběr fiktivního profilu je označený jako ukázka; volba rozhraní není přihlášení/oprávnění |
| M2 · měření, původ a potřebné trendy | Tým | todo | Opravit export a předat kontext ze stávajícího adaptéru; bez závislosti na K2b nebo novém registru léčby |
| M3 · šest situací a zprávy | Tým | todo | Konkrétní mezery textu/dotazníku, pečujícího a rozporů řešit stejným jádrem a koordinovat s rozpracovaným auditem K7 |
| M4 · doporučení a směrování | Tým | todo | Správný krok a kontakt podle běžné pracovní doby, zachované známé riziko; bez obecného přepisu orchestrace a doručovací fronty |
| M5 · ověření, demo a návrh integrace | Tým | todo | Průchod šesti situacemi a relevantní negativní případy, existující replay, záložní demo a stručný návrh MEDDI/EU provozu |

Následuje úplný backlog K1–K10, nikoli pořadí MVP. K2b, obecný K5,
spolehlivé doručování/převzetí a produkční K8/K10 jsou odložené; stav `todo`
zde neznamená podmínku dokončení MVP. K2a je uzavřená podpůrná část.
Lint a SMTP testy nejsou prioritou před fungujícím M1–M5.

| Krok / rozsah | Vlastník | Stav | Zbývající práce |
| --- | --- | --- | --- |
| K2a · trvalé přijetí události před LLM | Relace Codex | done | SQLite deník před LLM, stabilní ID, doslovný originál a metadata, vazby oprav a deduplikace; výpadky a čtení v novém procesu ověřené. Aditivní zavedení zachovává JSONy; obnovení dialogu zůstává K2b |
| K2b · trvalý dialog a revize | Tým | todo | Obnovit rozpracovaný kontakt ve stejném bodě bez opakování dokončených LLM volání; zachovat návrhy, potvrzení, opravy, nevyřešené vstupy i konečné/přerušené revize |
| K2c · měření a export | Tým | todo | Stejné zdrojované měření v triáži, historii a grafu; MASTER a cílené odpovědi oddělené, správný autor, opravy a deduplikace |
| K3 · časový kontext a skutečné podání léčby | Tým | todo | Odlišit plán/podání/druh cyklu, poslední chemo se zdrojem a odstupem; potřebné trendy předat i živému webu bez budoucích dat |
| K4 · aplikační orchestrace a bezpečnostní výstup | Tým | todo | Vyřešit konflikt zobrazení, vyhodnotit známé riziko před dalším cíleným LLM, uložit konečné i přerušené revize; chyba neztratí podklady |
| K5 · epizody, otázky a přeměření | Tým | todo | Klíčové/varovné nálezy, zlepšení a uzavření, společný plán kontrol, odpověď/remeasurement, běh v čase, neodpověď a deduplikace; schválené intervaly |
| K6/K8 · první průchod předání a kartičky | Tým | todo | M1 dodává kartičku a simulovaný přehled; nad rámec MVP zbývá trvalý požadavek se zdroji, prioritou, termínem, pokusy a převzetím |
| K6 · doporučení, kontakty, předání a souhrn | Tým | todo | Doplnit konkrétní nálezy/plány, vypočtené lhůty, předání/převzetí/opakování, pevnou předlohu souhrnu s LLM pouze pro formulaci a šablonovou zálohu |
| K7 · zprávy, nejistota a klinické mapování | Tým + mentor | todo | MASTER/importované zprávy stejnou cestou, konflikty/intervaly/nepokryté pojmy, schválené mapování škál; vyřešit O1–O10 backendu, neladit podle referenčních ID |
| K8 · pacientský a zdravotnický web | Tým | todo | Stručná kartička/detail/LLM stejné revize, kontroly, prioritní požadavky a zásahy týmu; role, volba zastupování a správné oslovení bez změny významu otázek |
| K9 · průběžný replay, úplný tok a demo | Tým | todo | Od K2 kontrolovat restart, opakované odeslání, opravy, výpadky a časovou izolaci; nakonec všech 171 check-inů a šest povinných situací včetně negativních/mezních případů, záchyt i zbytečné eskalace, srozumitelnost a záložní demo bez LLM |
| K10 · MEDDI a provoz v EU | Tým + pracoviště | todo | Integrační/provozní kontrakt, data a model v EU, přístupy, obnova, doručení, odpovědnosti a klinické převzetí; skutečné nasazení zvlášť |
| Lint · `meddi/disposition.py` | Tým | todo | Vyřešit dvě stávající ISC004 u spojovaných textů doporučení beze změny obsahu a ověřit Ruff |
| Testy · SMTP transport a formulář | Tým | todo | Doplnit chybějící automatické testy bez skutečného odesílání pro konfiguraci, CSRF, validaci adresy a selhání transportu; teprve potom uvést funkční příkaz v notifikačním README |

## Rozhodnutí podle rozsahu

Pro MVP řešit klinické nejasnosti, které mění jeho konkrétní případy;
všechny O1–O10 ani produkční otázky nejsou univerzální vstupní brána.
Neověřený klinický výklad zachovat viditelný, nevyřešit jej odhadem.

- K4: výslovně dořešit [konflikt okamžité kritické instrukce](decisions.md#otevřený-konflikt-bezpečnostního-výstupu)
  se skrýváním triáže až do potvrzení.
- K3/K5–K7: kvalifikovaně potvrdit [klinické a časové otázky O1–O10](backend.md#otevřené-klinické-otázky),
  zejména škály, rozpory definic, poslední podání, intervaly přeměření a dostupnost dat.
- K9/K10: s pořadateli ověřit formát/termín odevzdání a hodnoticí rozhraní;
  s pracovištěm kontakty, kalendář, cílové prostředí a odpovědnost za převzetí.

Kontroly a spouštěcí příkazy jsou v [architektuře](architecture.md#spuštění-a-kontroly).
Při změně úkolu aktualizovat jeho stav a odpovídající rozhraní/rozhodnutí,
nepřidávat nový historický audit se stejnými požadavky.
