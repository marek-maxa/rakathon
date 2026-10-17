# Platná rozhodnutí

Požadavky a jejich zdroje jsou v [zadání](challenge.md), cílové chování
v [plánu](meddi-onco-plan.md), implementované rozhraní v [architektuře](architecture.md).
Tento dokument uchovává volby důležité pro další vývoj; historii implementačních
relací, mergů a testovacích běhů nahrazuje Git.

| Oblast | Rozhodnutí | Důvod / důsledek |
| --- | --- | --- |
| Stack | Python 3.12 + uv, stávající Flask/Jinja/Plotly | Rozšiřovat hotové prvky; nový frontend ani framework není podmínkou |
| Rozsah MVP | Lokální syntetické demo, pořadí M1–M5 z plánu; K1–K10 zůstávají širší roadmapou | Přednost má viditelný průchod a správný výsledek; resume K2b, obecný plánovač, spolehlivé doručování a produkční zabezpečení odloženy |
| Vstup do MVP | Úvodní volba Pacient/Lékař, pacientský rozhovor a lékařský přehled mají oddělenou navigaci | Bez nového systému rolí; volba není autentizace a přepnutí nemaže stav rozhovoru |
| Identita pacienta | Pro demo výslovně označený fiktivní profil; cílově vlastní karta podle účtu nebo pozvánky, výběr více pacientů u lékaře | Přepnutí rozhraní patří do demo patičky; přihlašování/pozvánky jsou odložené po funkčním MVP |
| Klinické rozhodování | Jediné deterministické jádro `meddi/`; kořenová API a web jsou adaptéry | Nekopírovat klinické prahy do UI nebo LLM |
| Role LLM | Extrakce, formulace cílených otázek a odborné zprávy z pevné předlohy | Úroveň, trendy, příjemce, termíny a akce určí kód; zpráva má šablonovou zálohu |
| Výstup | Oddělit zdrojový signál, minimum, výslednou úroveň a úplnost | Nevyřešený údaj není nula/false; relevantní nevyhodnocené vstupy mají lidskou cestu, známé 3/4 se nesnižuje |
| MASTER | Odpověď je obdobou `zprava_pacienta`, nikoli jiná klinická politika | Zachovat otázku, autora/časy; zpráva má při rozporu přednost podle pravidel §6.2/§6.4 |
| Webový sběr | MASTER vybírá konkrétní relevantní otázky; využívá již sdělené údaje, doptá jen chybějící rozlišení; limit kontaktu 6 | Upřesnění týmu: celé dotazníky byly nechtěná změna web větve. Cílené podmíněné větve a společná kontrola zůstávají; úplné formuláře neobnovovat |
| Zpráva a rozpor | Historický check-in i nový kontakt používají stejný extraktor/jádro; aktuální úvodní nález nezmizí jen pozdější mírnější volbou | Cache je vázaná na přesný originál, nepotvrzená fakta zůstávají nepotvrzená. Explicitní oprava/odeznění potřebuje samostatnou politiku |
| CLI replay | Síťová extrakce pouze s `--with-messages`; výchozí běh a `--without-messages` zůstávají offline | Záměrná odchylka od web větve, aby běžná kontrola nespouštěla nečekaná API volání |
| Zdrojová barva | Zobrazovací barva nevyhodnocené odpovědi sama nevytváří předběžné červené/oranžové minimum | Nepokrytý význam zůstává k lidskému review; klinická pravidla a výstupní politika zůstávají autoritou |
| Sdílené demo | Basic Auth na všech cestách, bez přihlašovacích údajů vracet 503; balík pro Azure bez klíčů/reference/dat working copies | Společné heslo není individuální role. Jeden proces, stabilní secret a trvalý DATA_DIR; vzdálené nasazení není součást této integrace |
| Potvrzení | Pacient kontroluje slovní návrhy; web používá společné potvrzení a opravy | Potvrzují se vyřešené odpovědi, nikoli automaticky všechny extrahované fakty |
| P0 · naléhavá instrukce | Uživatel schválil samostatnou okamžitou instrukci při minimu 3/4; konečný výsledek zůstává po potvrzení a uložení | Nový závažný nález pozastaví další cílenou extrakci do výslovného pokračování. Známá instrukce přežije chybu LLM/zápisu a otevřenou opravu |
| Karta | Události a revize zachovávají původ; aktuální karta je odvozený pohled | Oprava ani zlepšení nesmažou historii; nebrat maximum celé historie |
| Nálezy | Nezelené nálezy sledovat jako epizody; zahrnout relevantní zlepšení a kontext | Aktuální varovné příznaky pro 3/4 jsou podmnožina klíčových, u 1/2 prázdné |
| Kontroly | Jedna evidence pro cílené otázky i přeměření | Vazba na epizodu, priorita, termín, stav a deduplikace; intervaly schvaluje klinická politika |
| Lékař | Stručná aktuální kartička, detail a LLM zpráva ze stejné revize | Nutný krok a zdroje viditelné bez čekání na LLM; starší zpráva je historická |
| M1 · přehled týmu | Kartička a `/team` jsou pohledy nad stejnými posledními hodnoceními; krátký souhrn tvoří šablona | Bez nové fronty a LLM; předání je označené jako simulované, neúplnost je oddělená od priority |
| M2 · měření a trendy | Export promítá vybrané validované vstupy stejného hodnocení; živý web přebírá trendy ze stávajícího adaptéru | Bez nového parseru, klinických prahů nebo registru léčby; rozporná měření zůstávají doložená, bez smyšleného bodu grafu. Nahrazené hodnoty zůstávají v intake |
| M4 · směrování | Čistý výpočet kontaktu a lhůty podle času hodnocení v Europe/Prague a pravidel §2/§5 | Po–Pá 7:00 včetně až 15:30 nezahrnuto; červená vždy 155, oranžová do 2 h nebo služba ihned, paliativní linka s náhradní pomocí. Nezmění klinickou úroveň, netvrdí doručení; svátky a výjimky pracoviště nejsou v dodaném kalendáři |
| Zastupování | Nenápadná volba pod otázkou, autor oddělený od subjektu potíží | Oslovení skutečného adresáta; křestní jméno a doložený rod, jinak neutrálně; kanonický význam otázky zachovat |
| Léčba a čas | Poslední skutečné podání doložit; plán, D1 a typ cyklu rozlišovat | Neznámá léčba není negativní kontext, budoucí údaje nepatří do hodnocení |
| Úložiště | SQLite deník původních událostí před LLM; potvrzené check-iny dál v atomických JSON working copies | Aditivní zavedení bez přepisu originálů; obnova dialogu/revize jsou K2b, produkční databáze K10 |
| Katalog | Explicitní katalog všech 49 otázek a zdrojové definice; zatím bez RAG | Podobnost není klinická jistota, tvrdá pravidla nesmějí záviset na top-k vyhledávání |
| Integrace | Datový a předávací adaptér oddělené od pravidel; MEDDI API během soutěže pouze navrhnout | SMTP demo není doručený klinický požadavek; ostrá data vyžadují ověřený EU provoz |
| Evaluace | Chronologický replay, reference a názvy scénářů mimo rozhodování/LLM | Nezávisle měřit záchyt i zbytečné eskalace; neladit pravidla podle ID nebo reference |

## Bezpečnostní výstup K4/M4

Uživatel výslovně zvolil okamžitou naléhavou instrukci. Původní pokyn
skrývat výslednou triáž dál platí pro běžný konečný výsledek; samostatné
doporučení při `minimum_color=orange/red` se zobrazí před potvrzením
i uložením. Vychází z doporučení stejného backendu, nikoli ze zobrazovací
barvy možnosti. Klinické prahy se tím nemění. Zdroj požadavku:
`documents/MEDDI – MEDDI Onco.pdf`, s. 6–7; pravidla triáže §1–3 a §6.4.

Po obecné extrakci úvodu, další odpovědi i opravy se nejprve spustí sdílená
triáž. První rozpoznané minimum 3/4 nebo zvýšení z 3 na 4 vrátí řízení do
webu před cíleným LLM; stejný již zobrazený pokyn nevyžaduje další potvrzení.
Doplnění je volitelné až po výslovném pokračování. Pokračování nezopakuje
obecnou extrakci. Běžný nezávažný tok zachovává cílené otázky a limit 6.

Známá naléhavá instrukce v témže kontaktu zůstává při chybě zpracování,
zápisu nebo otevřené opravě a nesníží se kvůli neúplnému novému návrhu.
Neprokazuje skutečné předání týmu ani vyhledání pomoci. Její uchování je
v paměti procesu; obnova po restartu, úplné revize a explicitní klinické
uzavření nálezu zůstávají mimo P0. Nejistota extrakce a klinické pokrytí
šesti situací se dál ověřují v M3. M4 doplňuje kontakty a lhůty podle času
hodnocení; historický replay nepřebírá aktuální systémové hodiny.

## Úložiště událostí K2a

Pro lokální deník původních zpráv zvoleno SQLite ze standardní knihovny,
kvůli transakcím a unikátním klíčům. Rozhraní `web.event_store.EventStore`
nezávisí na Flasku. Přijetí zdroje se dokončí před LLM a přežije jeho chybu;
opakované odeslání vrací původní ID/čas, oprava dostane nové ID s vazbou.
Podepsaný identifikátor formuláře váže odeslání na pacienta, kontakt,
browser session a skutečnou otázku; není náhradou autentizace.

Zavedení je aditivní: nové události v `DATA_DIR/events.sqlite3`, potvrzené
check-iny dál v JSON working copies. Existující JSONy ani organizátorské
zdroje se nepřepisují a nedoplňuje se do nich vymyšlený původ. Schéma deníku
má verzi 1, neznámé verze se odmítají. Obnovení dialogu a výsledky zpracování
zůstávají odloženým K2b; volba produkční databáze zůstává součástí K10 s MEDDI.
K2a nyní nerozšiřovat: jeho původní priorita před produktovými funkcemi byla
pro MVP nepřiměřená. Existující ověřenou část ponechat uzavřenou a další
kapacitu věnovat M1–M5; neprovádět další přestavbu úložiště před demonstrací.

## Minimální plán notifikací

Výslovně schválené malé rozšíření K5: jeden opakovaný dotazník na pacienta,
ručně určený interval a nejvýše jedna připomínka při neodpovědi.
Žádné odvození intervalu z barvy nebo LLM. Plány sdílejí `events.sqlite3`,
ale mají vlastní verzi schématu; deník zdrojových událostí se nemění.
Samostatný příkaz kontroluje potvrzené JSONy před SMTP; naplánování
a periodické spouštění je explicitní, ne při startu Flasku.
