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
| Audit nadměrné eskalace a pokrytí, K7/K9; answer_coverage, triage, testy | Relace web | doing | Oddělení zobrazovacích barev od triáže je již hotové. Vysvětlit zbývající zvýšené výsledky a neúplnost; běžné/mírné odpovědi a větvení skutečně vyhodnotit. Neskrývat texty, neznámá měření či chybějící odpovědi kvůli více zeleným. Ověřit celou časovou sadu i syntetické proti-příklady bez referencí v rozhodování |
| Dokončit ověření konkrétního kroku pro každé hodnocení, část K6; disposition, pipeline, web a testy | Relace web | doing | Současná výstupní politika již existuje; ověřit všechny vstupní cesty a uložené výsledky. Úroveň 1–4, krok a kontakt, neúplnost zvlášť, známé 3/4 zachované; neaktivní hypotetická pravidla neeskalují rutinní kontakt |

## Navazující implementace

Prioritou je MVP podle [omezeného rozsahu M1–M5](meddi-onco-plan.md#aktuální-rozsah-mvp).
K1 a K2a existují; na K2a nyní nenavazovat obnovou dialogu K2b.
M1 a M2 jsou hotové. Zprávy, rozpory a cílený otázkový tok jsou propojené;
M3 ale ještě není klinicky ověřené pro všech šest situací. Priority níže
mají přednost před pořadím širšího backlogu. P0 je hotové; následuje P1,
ověření šesti situací a auditu K7/K9.

| Pořadí MVP | Vlastník | Stav | Podmínka dokončení |
| --- | --- | --- | --- |
| M1 · kartička a přehled požadavků | Relace Codex | done | Kartička v reportu a `/team`, důvod/krok/kontakt/čas/zdroj stejného posledního hodnocení; šablonový souhrn a označená simulace předání. Přehled řadí požadavky podle výsledné úrovně; neúplnost zobrazuje zvlášť |
| UI · vstup Pacient / Lékař | Relace Codex | done | Úvodní volba na `/`, rozhovor na `/patient`, lékařský přehled na `/team`; přepnutí v demo patičce zachová rozhovor. Výběr fiktivního profilu je označený jako ukázka; volba rozhraní není přihlášení/oprávnění |
| M2 · měření, původ a potřebné trendy | Relace Codex | done | Vybraná ověřená měření v triáži, uložené historii a grafu; MASTER/cílené odpovědi a autor odděleně. Živý web přebírá zdrojované trendy a léčebný kontext stávajícího adaptéru; bez K2b a nového registru léčby |
| M3 · šest situací a zprávy | Tým + mentor | doing | Integrační část hotová; zbývá nezávislý průchod šesti situacemi a negativními případy, kvalita extrakce a doložené klinické mezery. Koordinovat s auditem K7, neopakovat zavedení zpráv |
| M4 · doporučení a směrování | Aktuální relace Codex | done | Kontakty a lhůty podle Europe/Prague, hranic 7:00/15:30, víkendů a doložené paliativní péče; červená vždy 155, zvláštní lhůty zachované. P0, výsledek a kartička používají stejné hodnocení. 880 testů včetně 34 směrovacích scénářů prošlo; Ruff a Azure ZIP ověřeny. Svátky/výjimky pracoviště a skutečné doručování zůstávají mimo MVP |
| M5 · ověření, demo a návrh integrace | Tým | todo | Průchod šesti situacemi a relevantní negativní případy, existující replay, záložní demo a stručný návrh MEDDI/EU provozu |

Následuje úplný backlog K1–K10, nikoli pořadí MVP. K2b, obecný K5,
spolehlivé doručování/převzetí a produkční K8/K10 jsou odložené; stav `todo`
zde neznamená podmínku dokončení MVP. K2a je uzavřená podpůrná část.
Lint a SMTP testy nejsou prioritou před fungujícím M1–M5.

| Krok / rozsah | Vlastník | Stav | Zbývající práce |
| --- | --- | --- | --- |
| K2a · trvalé přijetí události před LLM | Relace Codex | done | SQLite deník před LLM, stabilní ID, doslovný originál a metadata, vazby oprav a deduplikace; výpadky a čtení v novém procesu ověřené. Aditivní zavedení zachovává JSONy; obnovení dialogu zůstává K2b |
| K2b · trvalý dialog a revize | Tým | todo | Obnovit rozpracovaný kontakt ve stejném bodě bez opakování dokončených LLM volání; zachovat návrhy, potvrzení, opravy, nevyřešené vstupy i konečné/přerušené revize |
| K2c · měření a export | Tým | todo | Základ dodává M2; dále úplná historie jednotlivých měření uvnitř kontaktu a napojení průběžných revizí K2b. Nahrazené hodnoty nyní zůstávají v intake, ne jako další body grafu |
| K3 · časový kontext a skutečné podání léčby | Tým | todo | M2 předává živému webu existující trendy bez budoucích dat; zbývá odlišit plán/podání/druh cyklu, doložit poslední chemo a odstup |
| K4 · aplikační orchestrace a bezpečnostní výstup | Tým | todo | P0 řeší zobrazení a kontrolu rozpoznaného rizika před cíleným LLM; zbývají úplné průběžné/přerušené revize a explicitní klinické uzavření opravy/odeznění |
| K5 · epizody, otázky a přeměření | Tým | todo | Klíčové/varovné nálezy, zlepšení a uzavření, společný plán kontrol, odpověď/remeasurement, běh v čase, neodpověď a deduplikace; schválené intervaly |
| K6/K8 · první průchod předání a kartičky | Tým | todo | M1 dodává kartičku a simulovaný přehled; nad rámec MVP zbývá trvalý požadavek se zdroji, prioritou, termínem, pokusy a převzetím |
| K6 · doporučení, kontakty, předání a souhrn | Tým | todo | Doplnit konkrétní nálezy/plány, vypočtené lhůty, předání/převzetí/opakování, pevnou předlohu souhrnu s LLM pouze pro formulaci a šablonovou zálohu |
| K7 · zprávy, nejistota a klinické mapování | Tým + mentor | todo | Společná cesta MASTER/importovaných zpráv a metadata rozporů existují; doplnit klinické pokrytí intervalů/nepokrytých pojmů a schválené mapování škál; vyřešit O1–O10 backendu, neladit podle referenčních ID |
| K8 · pacientský a zdravotnický web | Tým | todo | Stručná kartička/detail/LLM stejné revize, kontroly, prioritní požadavky a zásahy týmu; role, volba zastupování a správné oslovení bez změny významu otázek |
| K9 · průběžný replay, úplný tok a demo | Tým | todo | Od K2 kontrolovat restart, opakované odeslání, opravy, výpadky a časovou izolaci; nakonec všech 171 check-inů a šest povinných situací včetně negativních/mezních případů, záchyt i zbytečné eskalace, srozumitelnost a záložní demo bez LLM |
| K10 · MEDDI a provoz v EU | Tým + pracoviště | todo | Integrační/provozní kontrakt, data a model v EU, přístupy, obnova, doručení, odpovědnosti a klinické převzetí; skutečné nasazení zvlášť |
| UI · e-mail a výsledek dotazníku | Aktuální relace | done | Uložený kontakt.email, ruční pozvánka k vyplnění dotazníku od ošetřujícího lékaře a výrazný barevný výsledek zachované spolu s analýzou zpráv; SMTP testy bez skutečného odesílání |

## Hotové převzaté části — znovu nezadávat

- MASTER vybírá jen relevantní otázky. Již sdělené údaje se využijí bez
  opakování otázky, chybějící rozlišení se doptá; podmíněné větve, společná
  kontrola/opravy a původní limit 6 zůstávají. Celé formuláře byly nechtěná
  změna větve web a nejsou součástí schváleného toku.
- Úvodní nález při pozdější mírnější volbě nezmizí. Přijetí před LLM,
  stabilní ID/deduplikace, `/team` a zdrojovaná měření M2 zůstávají zachované.
- Historické zprávy mají extrakci, cache v pracovní kopii, kontrolu přesné
  shody zdroje, rozpory/doptání a viditelné selhání. Report je spouští explicitním
  chráněným POST; CLI má `--with-messages`, výchozí běh zůstává offline.
- Barva možnosti není klinická úroveň. Nepokryté vstupy zůstávají k review.
  Dvě chyby ISC004 v disposition jsou opravené.
- Společné heslo dema, Azure runtime balík a konfigurace datového adresáře
  existují. Individuální role, vzdálené nasazení a produkční převzetí hotové nejsou.

## Priority do dokončení MVP

| Priorita | Co nyní dokončit | Přijímací podmínka |
| --- | --- | --- |
| P0 · bezpečnostní bod K4/M4 · done | Relace Codex: uživatel schválil okamžitou naléhavou instrukci; checkpoint po obecné extrakci úvodu/odpovědi/opravy, před cíleným LLM; instrukce přežije chybu LLM/zápisu | Rozpoznané minimum 3/4 se zobrazí bez potvrzení/uložení; další doplnění až po výslovném pokračování, bez opakované obecné extrakce. Běžný konečný výsledek zůstává po potvrzení |
| P1 · M3 + audit K7/K9 | Ověřit šest povinných situací přes zprávy i formuláře, pečujícího a negativní/mezní případy; vysvětlit změněné eskalace | Známá tvrdá minima zachovaná, žádné reference ve vstupu; doložené důvody pro nižší/vyšší výsledky, klinické nejasnosti potvrzené mentorem |
| P2 · M4 · done | Konkrétní krok/kontakt a termín podle Europe/Prague, včetně mimo pracovní dobu a doložené paliativní péče | Běžný týdenní kalendář, historický čas zachovaný, minimum/úplnost beze změny; kalendář svátků a výjimek pracoviště před provozem potvrdit |
| P3 · M5 | Pacient → potvrzený výsledek → kartička/přehled, záložní demo bez LLM, návrh MEDDI/EU a odevzdání | Opakovatelné demo se šesti situacemi; ověřit čitelnost, termín/formát a případné sdílené demo v cílovém prostředí |

V M3 sledovat počet relevantních otázek a zbytečné opakování; celé formuláře
neobnovovat. Výběr otázky neblokuje vyhodnocení faktů mimo katalog. Neobnovovat před MVP K2b ani stavět nový plánovač,
doručovací frontu, systém individuálních účtů nebo obecný registr léčby.
Azure balík není povinnost nasadit ani potvrzení vhodnosti cílové oblasti;
pro soutěžní demo lze zůstat lokálně nad syntetickými daty.

## Rozhodnutí podle rozsahu

Pro MVP řešit klinické nejasnosti, které mění jeho konkrétní případy;
všechny O1–O10 ani produkční otázky nejsou univerzální vstupní brána.
Neověřený klinický výklad zachovat viditelný, nevyřešit jej odhadem.

- K4: zachovat schválené oddělení [naléhavé instrukce a konečného výsledku](decisions.md#bezpečnostní-výstup-k4m4);
  úplné revize a klinické uzavření nálezu zůstávají mimo P0.
- K3/K5–K7: kvalifikovaně potvrdit [klinické a časové otázky O1–O10](backend.md#otevřené-klinické-otázky),
  zejména škály, rozpory definic, poslední podání, intervaly přeměření a dostupnost dat.
- K9/K10: s pořadateli ověřit formát/termín odevzdání a hodnoticí rozhraní;
  s pracovištěm kontakty, kalendář, cílové prostředí a odpovědnost za převzetí.

Kontroly a spouštěcí příkazy jsou v [architektuře](architecture.md#spuštění-a-kontroly).
Při změně úkolu aktualizovat jeho stav a odpovídající rozhraní/rozhodnutí,
nepřidávat nový historický audit se stejnými požadavky.
