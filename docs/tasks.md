# Otevřené úkoly MEDDI ONCO

Stavy: `todo`, `doing`, `blocked`, `done`. Jeden vlastník na úkol.
Hotovou implementaci popisuje [architektura](architecture.md), podmínky kroků
[plán](meddi-onco-plan.md#implementační-kroky-a-závislosti).
Dokončené provozní zápisy a historii testovacích běhů zde neudržujeme.

Pracovní uzávěrka: **17. 10. 2026 13:00 Europe/Prague (11:00 UTC)**,
odvozená z uživatelova „za 3 hodiny přesně“ převzatého kolem 10:00.
Prezentace zatím bez pevného časového limitu; předvést existující MVP.
Formát/místo odevzdání a požadavek na veřejnou URL ještě nejsou upřesněné.

Přijímací sada v `tests/acceptance_meddi/` má kontrolu zdrojů přenositelnou
mezi LF/CRLF checkouty. Její validace není ověřením splnění aplikací;
napojení skutečného adaptéru a vyhodnocení zůstává součástí auditu K7/K9.

Aktuální zaměření podle posledního pokynu uživatele: **funkce dema,
sledování v čase a souvislostech, přehledné a působivé rozhraní lékaře**.
Pacientský vzhled zachovat. Rozhodující je pořadí D1–D4 níže; technické
zpevňování backendu a produkční bezpečnost nejsou nyní prioritou.
[Kontrola proti oficiálnímu zadání a konkrétní mezery](meddi-onco-plan.md#funkční-kontrola-proti-zadání).

## Rozpracovaná práce

Tyto dvě práce zachovávají původní vlastnictví relace web; nepřebírat je
souběžným zápisem do stejného checkoutu.

| Úkol | Vlastník | Stav | Podmínka dokončení |
| --- | --- | --- | --- |
| Audit nadměrné eskalace a pokrytí, K7/K9; answer_coverage, triage, testy | Relace web | doing | Oddělení zobrazovacích barev od triáže je již hotové. Vysvětlit zbývající zvýšené výsledky a neúplnost; běžné/mírné odpovědi a větvení skutečně vyhodnotit. Neskrývat texty, neznámá měření či chybějící odpovědi kvůli více zeleným. Ověřit celou časovou sadu i syntetické proti-příklady bez referencí v rozhodování |
| Dokončit ověření konkrétního kroku pro každé hodnocení, část K6; disposition, pipeline, web a testy | Relace web | doing | Současná výstupní politika již existuje; ověřit všechny vstupní cesty a uložené výsledky. Úroveň 1–4, krok a kontakt, neúplnost zvlášť, známé 3/4 zachované; neaktivní hypotetická pravidla neeskalují rutinní kontakt |

Pro audit K7/K9 je nyní doložené [mentorovo upřesnění O10](backend.md#upřesnění-mentora-k-o10),
předané uživatelem 17. 10. 2026: nemožnost přijmout/udržet tekutiny
z libovolné příčiny + známky dehydratace znamená 4; u ONC-011-C09 navazuje
na doložené selhání příjmu předchozího dne. Sdílené jádro nyní vyhodnotí nemožnost příjmu i udržení tekutin a známky
dehydratace včetně tepu >100 a systolického tlaku <90; regrese jsou v
`tests/test_dehydration_clarification.py`. Offline adaptér rozpozná omezený
slovník výslovných sdělení pacienta a návaznost předchozího dne při aktuální
zprávě o včerejším pití a přetrvávající těžké poruše polykání (afty index 3).
Skutečný průchod ONC-011 C08 → 3, C09 → 4 má regresi bez LLM/referencí;
obecné porozumění zprávám a řízení všech epizod tím není vyřešené.
Původní vlastnictví auditu zůstává zachované; samotné závratě a málo moči
bez doloženého selhání příjmu se podle mentora nepovyšují na 4.

## Zdrojové přijímací scénáře

Finální technická kontrola podle pokynu uživatele z 17. 10. 2026 je
[doložená zde](final-check.md): všech šest situací znovu prošlo automatickými
kontrolami, 64 cílených / 985 celkem. Po opravě pomocného testu na následný
pokyn uživatele jsou doložené tři živé průchody extrakce → triáž (horečka,
průjem a dcera), celkem čtyři sekvenční API volání včetně prvního
neúspěšného testu horečky. Opravená horečka šla přes skutečný dialog do
červeného checkpointu před cíleným dotazováním; 5 cílených regresí prošlo.
Žádná změna aplikační logiky.
Klinické převzetí a původní vlastnictví K6/K7/K9 zůstávají otevřené.

| Úkol | Vlastník | Stav | Podmínka dokončení |
| --- | --- | --- | --- |
| Připravit nezávislé testy pravidel a prezentací | Aktuální relace Codex | done | [Sada](../tests/acceptance_meddi/README.md): 502 syntetických scénářů / 140 požadavků, oddělené vstupy a očekávání, zdroj u každého případu, pokrytí šesti situací z PDF s. 9, hranic, negací a časové dostupnosti. Kontrola sady a hodnoticí nástroj existují; splnění aplikací se netvrdí |
| Napojit a splnit zdrojovou přijímací sadu | Navazující agent + mentor | todo | Tenký adaptér skutečné aplikace, doložené výsledky zvlášť pro offline a živé LLM; opravy aplikace bez opisování očekávání. Klinické/textové review předat člověku; zachovat vlastnictví probíhajícího auditu K7/K9 a K6 |

## Navazující implementace

Prioritou je MVP podle [omezeného rozsahu M1–M5](meddi-onco-plan.md#aktuální-rozsah-mvp).
K1 a K2a existují; na K2a nyní nenavazovat obnovou dialogu K2b.
M1 a M2 jsou hotové. M3 má implementovaný běžný tok, pečujícího i technické
průchody šesti situacemi s negativními případy; zbývá klinické převzetí
mentorem. P0 a M4 jsou hotové. Původní audit K7/K9 zůstává otevřený.
P3 má implementovaný funkční pacientský portál včetně vizuální kontroly
na mobilu a desktopu. M5 má připravený demo podklad, samostatnou offline
zálohu, základní souhrn ověření a integrační návrh; zbývá převzetí/nácvik
a potvrzení zbývajících organizačních údajů. Živě byly ověřené formulářové
handlery, opraveno ztrácení „právě“ naměřené teploty, neodpověditelná
horečková otázka pod rozsahem možností a časové zpracování „náhle“.
MUST HAVE optimalizace LLM je až poslední
implementační krok, po ustálení funkcí a prezentačních podkladů.

| Pořadí MVP | Vlastník | Stav | Podmínka dokončení |
| --- | --- | --- | --- |
| M1 · kartička a přehled požadavků | Relace Codex | done | Kartička v reportu a `/team`, důvod/krok/kontakt/čas/zdroj stejného posledního hodnocení; šablonový souhrn a označená simulace předání. Přehled řadí požadavky podle výsledné úrovně; neúplnost zobrazuje zvlášť |
| UI · vstup Pacient / Lékař | Relace Codex | done | Úvodní volba na `/`, portál na `/patient`, lékařský přehled na `/team`; přepnutí rozhraní v demo patičce zachová rozhovor. Demo kód vybírá fiktivní profil, změna účtu/odhlášení rozhovor ukončí; volba rozhraní není přihlášení/oprávnění |
| M2 · měření, původ a potřebné trendy | Relace Codex | done | Vybraná ověřená měření v triáži, uložené historii a grafu; MASTER/cílené odpovědi a autor odděleně. Živý web přebírá zdrojované trendy a léčebný kontext stávajícího adaptéru; bez K2b a nového registru léčby |
| M3 · šest situací a zprávy | Tým + mentor | doing | Technická implementace a průchody šesti situací/mezí hotové, včetně „dobrý“, pečujícího a paliativního kontextu; živá syntetická kontrola extrakce provedena. Pro úplné uzavření zbývá nezávislé kvalifikované klinické převzetí, nikoli další zavedení integrační cesty |
| M4 · doporučení a směrování | Aktuální relace Codex | done | Kontakty a lhůty podle Europe/Prague, hranic 7:00/15:30, víkendů a doložené paliativní péče; červená vždy 155, zvláštní lhůty zachované. P0, výsledek a kartička používají stejné hodnocení. 880 testů včetně 34 směrovacích scénářů prošlo; Ruff a Azure ZIP ověřeny. Svátky/výjimky pracoviště a skutečné doručování zůstávají mimo MVP |
| MUST HAVE · pacientský portál | Aktuální relace Codex | done | Demo kód, oddělené účty/odhlášení, MASTER, uložený stav/krok/čas, vlastní údaje a historie. Konkrétní otázky/měření/nálezy ze zprávy se vracejí do stejné triáže; společné kontroly s explicitním plánem. Automatické průchody a HTML 14 profilů ověřeny, vizuální kontrola 390/1440 px i prohlížečový cyklus odpovědi hotové. [Rozsah a průchod](meddi-onco-plan.md#must-have-pacientský-portál) |
| M5 · ověření, demo a návrh integrace | Aktuální relace Codex | doing | [Demo podklad a návrh integrace](demo.md), obnovený offline export šesti situací, automatické průchody a vizuální/prohlížečová kontrola hotové. Plán → neodpověď → pacientská odpověď → další termín prošel bez JS chyb, s náhradou LLM a blokovaným SMTP. Zbývá klinické převzetí a původní audit, závěrečný nácvik s živou konfigurací, formát/místo odevzdání a případná veřejná URL |
| MUST HAVE · rychlost LLM · poslední krok | Tým | todo | Až po funkcích a přípravě M5 změřit celý krok i počet/dobu volání; porovnat dostupný menší/rychlejší model, podporované nižší uvažování a odstranit zbytečná volání. Zapsat srovnání rychlosti i správnosti, po změně zopakovat relevantní ověření a finální nácvik. [Podmínky](meddi-onco-plan.md#must-have-rychlost-llm-pro-prezentaci) |

Následuje úplný backlog K1–K10, nikoli aktuální pořadí D1–D4. K2b, obecný K5,
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
| Notifikace · minimální plán | Aktuální relace | done | Ruční interval a jedna připomínka v events.sqlite3, CLI schedule/list/cancel/run, kontrola potvrzených JSONů před odesláním, další cyklus po vyplnění; medicínská pravidla a automatické spouštění zatím bez konfigurace |
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
- Přepnutí pacient/pečující je nenápadné textové tlačítko pod otázkou s návratem
  na jedno kliknutí; původní checkbox a tlačítko „Změnit autora“ jsou nahrazené.

## Priority do dokončení MVP

Pořadí pro zbývající čas je funkční návaznost → lékařský přehled a souhrn →
převzetí situací → finální ladění. P0, základ M1/M2/M4 a pacientský portál
existují a při doplňování se zachovají. D1/D2 jsou implementované a ověřené;
D3/D4 zachovávají níže uvedené zbývající podmínky. Zdrojové posouzení je v
[plánu](meddi-onco-plan.md#funkční-kontrola-proti-zadání).

| Priorita / stav | Co nyní dokončit | Přijímací podmínka |
| --- | --- | --- |
| D1 · funkční sledování v čase · done | Aktuální relace Codex: kontroly zahrnují nálezy pouze ze zprávy; ruční termín/interval/pokyn v lékařském UI, společná neodpověď a navazující termín po uložené odpovědi | Časová historie plánu a splnění nepropouští budoucnost. Bez intervalu je kontrola jednorázová; neodpověď nemění klinickou barvu. Regrese i prohlížečový cyklus prošly; existující vícedenní scénáře průjmu a hmotnosti/ortopnoe zůstávají zelené. S1 s. 5/9/12; S4 §4–6 |
| D2 · lékařský přehled, souhrn a vzhled · done | Aktuální relace Codex: kompaktní /team, priority/termíny, hledání/filtry, změna naléhavosti; souhrn s citací/autorem, léčbou, doloženými trendy, časovou osou a plánem/kontaktem | Zkontrolováno v Chrome 1440/390 px bez vodorovného přetečení. Klinická úroveň používá stávající hodnocení; úplné podklady v rozbalení, Plotly až na vyžádání bez JS chyb. S1 s. 5/11/12; S2 slidy 2–3/5; S7 |
| D3 · převzetí klíčových funkcí dema · doing | Aktuální relace Codex + mentor: automatické průchody šesti situací/běžného/nejasného stavu/rozporu i nového následného doplnění prošly; zůstává kvalifikované klinické převzetí a původní audit K7/K9 a K6 | Celá aktuální pytest sada 985 passed. Prohlížečový průchod včetně další kontroly je doložen lokálně s náhradou LLM a blokovaným SMTP; neprokazuje novou živou extrakci ani splnění 502 přijímacích scénářů aplikací. S1 s. 9–10 |
| D4 · závěrečné ladění a nácvik · doing | Aktuální relace Codex + tým: grafy odložené mimo první načtení souhrnu; vzhled a cyklus pacient → sledování → lékař zkontrolované; offline záloha šesti situací obnovena | Zbývá porovnání rychlosti/správnosti skutečně dostupných LLM konfigurací a finální živý nácvik; model se touto změnou neměnil. Organizační údaje odevzdání zůstávají k potvrzení. Základ M5 už existuje v [demo.md](demo.md) |

### Nejbližší postup po funkční kontrole

1. D1: určit na dvou konkrétních příbězích, co a kdy se má znovu získat,
   jak se pozná nová odpověď a co uvidí tým při neodpovědi. Doplnit jen
   mezery tohoto průchodu. Samostatný SMTP plánovač není klinické sledování.
2. D2: nad stejnými příběhy sestavit stručný lékařský souhrn a navrhnout
   přehled/detail. U každé změny ukázat minulý → současný údaj, datum,
   kontext a očekávaný krok. Pacientské UI projít, rozsáhle nepřekreslovat.
3. D3: projet zbývající situace z PDF s. 9 a běžný/nejasný stav; opravovat
   konkrétní chyby viditelného toku. Zachovat odpovědnost rozpracovaných
   auditů; klinické převzetí ani celkový audit se neoznačují za hotové.
4. D4: až poté rychlost LLM, kosmetické detaily a finální nácvik. Offline
   export vytvoří `uv run --locked python -m scripts.build_demo`; návrh
   integrace už je v podkladu. Nové MEDDI API nebo nasazení není nynější úkol.

V M3 sledovat počet relevantních otázek a zbytečné opakování; celé formuláře
neobnovovat. Výběr otázky neblokuje vyhodnocení faktů mimo katalog. Neobnovovat
před MVP K2b ani stavět nový plánovač, doručovací frontu, systém skutečných
individuálních účtů nebo obecný registr léčby. Simulovaný demo vstup a
jednoduché uložené kontroly/připomenutí v portálu zůstávají v rozsahu D1.
Azure balík není povinnost nasadit ani potvrzení vhodnosti cílové oblasti;
pro soutěžní demo lze zůstat lokálně nad syntetickými daty.

### Obecná odpověď na MASTER

Implementace v `llm_intake/master.py`, `dialogue.py` a `meddi/pipeline.py`;
webové průchody v `tests/test_mvp_scenarios.py`. Platí:

1. Rozpoznat kladné celkové hodnocení v kontextu skutečné MASTER otázky
   jako informaci o celkovém stavu. „Dobrý“ neznamená nulu všech příznaků
   ani automatické číslo škály.
2. Když přesná hodnota chybí, nabídnout jedinou existující otázku
   `nezadouci_ucinky/pocit` (1–5), místo ukončení sběru bez otázek.
   Nepředvyplnit odhadnutý index ani otevírat celý dotazník.
3. Po skutečné potvrzené odpovědi provázat původní obecné hodnocení s tímto
   upřesněním; nemá dál samo zůstávat nevyhodnoceným klinickým problémem.
   Ostatní nevyřešené příznaky/rozpory tím nesmějí zmizet.

Ověřený průchod: „dobrý/dobře/dobre“ s následnou přesnou běžnou hodnotou a bez
dalšího podkladu rizika skončí dalším sledováním, nikoli automatickým
kontaktem týmu. Testy pokrývají obě varianty extrakce (žádný fakt / slovní celkový
stav). „Dobrý, ale…“ s rizikovým nálezem zachová vyšší minimum; prázdná
odpověď, „nevím“, neznámý subjekt a selhání modelu se neprohlásí za zelené.
Používá se existující jádro a celý webový průchod s náhradou LLM.
Globální výjimka `no_facts → green` ani nové klinické prahy se nezavedly.

`done` · Doplnění obecného nepříznivého stavu: „blbě/špatně → 4“ nabídne
žádost o konkrétní popis potíží a jeho normální extrakci, nové otázky a P0.
Indikátor `message_specificity` uchová důvod a pokusy; nejasnost po limitu
zůstane k review. „Dobře → 1/2“ včetně parafráze nezíská další obecný dotaz,
skóre 5 zachovává původní naléhavou cestu. Webové/CLI syntetické regrese
jsou v `test_mvp_scenarios.py` a `test_master_dialogue.py`; živý LLM tím
ověřen není. Zdroje: pravidla §6.4; PDF s. 5 a 7.

### Přijímací průchod šesti situacemi P1

Zdrojem situací je `documents/MEDDI – MEDDI Onco.pdf`, s. 9; evaluace
s. 10–11. `tests/test_mvp_scenarios.py` ověřuje celé webové průchody včetně
normálních/mezních protějšků, původu, limitu otázek, uložení a shody výsledku
s reportem/přehledem. Součástí je více kontaktů v čase i zlepšení. Omezená
živá kontrola používá jen syntetické zprávy; výstup je lokálně v ignorovaném
`.scratch/m3-live-extraction.json`. Tyto kontroly nenahrazují kvalifikované
klinické převzetí, proto M3 zatím není označené celé jako `done`.

| Situace | Implementovaný automatický průchod | Co potvrdit klinicky / další hranice |
| --- | --- | --- |
| Horečka po léčbě | Text → měření → červená/kartička; hranice 37,9/38 °C a zdroj D1 | Použití D1 není úplný registr skutečných podání (O7) |
| Zhoršující se kolitida na imunoterapii | Dny s 2 → 5 → 2 stolicemi nad normál, bolest břicha, zlepšení; hranice 3/4 | Převzít časové a klinické interpretace; neznámé okno zůstává k review |
| Plíživé srdeční obtíže | Hmotnost z dostupné historie, hranice +2 kg, následná nová ortopnoe | Převzít kontext léčby a časový průběh; obecný registr epizod se nezavádí |
| Interakce a krvácení | Kapecitabin/warfarin, krev ve stolici a nové modřiny; budoucí lék se nepoužije | Nejde o obecný interakční engine; nespecifikované místo se nevymýšlí |
| Paliativní pacientka a dcera | Volba/autorství v UI, oddělení zátěže, zdroj záměru léčby, 24h tým/hospic se záložní 155, červená zachovaná; přání pro lékaře | Potvrdit konkrétní paliativní linku a platnost přání; jejich text nerozhoduje o snížení úrovně |
| Rozpor zprávy a dotazníku | Mírnější volba neodstraní horečku, souhlasící volba nevytváří rozpor | Nezávisle převzít chování; obecné explicitní uzavření/odeznění zůstává K4/K7 |

Podpůrný ruční e-mail a připravený Azure balík jsou dokončené dílčí změny.
Před P1/P2 je dál nerozšiřovat bez konkrétní potřeby tohoto průchodu.
Předání zůstává simulované, skutečné doručení a vzdálený provoz neověřené.

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
