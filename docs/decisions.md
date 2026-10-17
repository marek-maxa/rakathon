# Platná rozhodnutí

Požadavky a jejich zdroje jsou v [zadání](challenge.md), cílové chování
v [plánu](meddi-onco-plan.md), implementované rozhraní v [architektuře](architecture.md).
Tento dokument uchovává volby důležité pro další vývoj; historii implementačních
relací, mergů a testovacích běhů nahrazuje Git.

| Oblast | Rozhodnutí | Důvod / důsledek |
| --- | --- | --- |
| Stack | Python 3.12 + uv, stávající Flask/Jinja/Plotly | Rozšiřovat hotové prvky; nový frontend ani framework není podmínkou |
| Rozsah MVP | Lokální syntetické demo, M1–M5 doplněné o MUST HAVE portál a rychlost LLM; K1–K10 zůstávají širší roadmapou | Přednost má viditelný průchod a správný výsledek; resume K2b, obecný plánovač, spolehlivé doručování a produkční zabezpečení odloženy |
| Aktuální pořadí dema D1–D4 | D1 funkční sledování v čase a souvislosti, D2 lékařský přehled/souhrn/vzhled, D3 převzetí klíčových situací, D4 rychlost a finální nácvik | Poslední pokyn uživatele přesouvá důraz na viditelné funkce dema. Pacientský vzhled zachovat, technické zpevňování a produkční bezpečnost odložit. Původní audity zachovávají vlastníky; souhrn do 30 sekund a kontext mají zdroj v PDF s. 5/12 a PPTX slidech 2–3/5. Podrobná mezera a podmínky jsou v plánu a úkolech |
| Vstup do MVP | Úvodní volba Pacient/Lékař, pacientský rozhovor a lékařský přehled mají oddělenou navigaci | Bez nového systému rolí; volba není autentizace a přepnutí nemaže stav rozhovoru |
| Identita pacienta | Implementovaná simulace přihlášení demo kódem syntetického profilu; ukázkové účty jsou v odděleném demo ovládání | Nahrazuje běžný pacientský výběr jmen. Změna účtu/odhlášení zneplatní starý rozhovor a tokeny, uložená data zachová. Skutečné účty, oprávnění, pozvánky a obnova hesla jsou dál odložené |
| Pacientský portál · MUST HAVE | Kompaktní vlastní prostředí: MASTER, stav a další krok, sledované potíže/měření, konkrétní kontroly/připomenutí a stručný profil | Výslovný požadavek uživatele; stejná uložená hodnocení jako reporting. Jen malý uložený seznam kontrol s přímým vstupem odpovědi/měření, bez obecného plánovače a externích notifikací; intervaly mají doložený podklad |
| Kontroly v portálu · MVP | Malá evidence v JSON working copy, atomicky aktualizovaná s potvrzeným check-inem; GET jen odvozuje pohled | Návrh z dostupných odpovědí/měření i nálezů pouze ze zprávy, žádné odhadnuté intervaly. Aktualizace vyžaduje nový konkrétní uložený údaj; neznačí klinické odeznění. Přímá otázka vstupuje do stejné extrakce/triáže a zachová P0; mobil/desktop vizuálně ověřeny |
| Odezva LLM · MUST HAVE, poslední krok | Teprve po funkcích a přípravě M5 změřit celý tok a porovnat dostupný menší/rychlejší model, podporované nastavení uvažování a počet volání; po změně ověřit a nacvičit demo | Model se zatím nemění a měření se nezadává jako dřívější samostatný úkol. Vybrat podle rychlosti i správnosti na stejné syntetické sadě; zachovat tvrdá minima, potřebné otázky a P0. Podrobnosti jsou v plánu |
| Klinické rozhodování | Jediné deterministické jádro `meddi/`; kořenová API a web jsou adaptéry | Nekopírovat klinické prahy do UI nebo LLM |
| O10 · mentorovo upřesnění | Selhání příjmu nebo udržení tekutin z libovolné příčiny se známkami dehydratace znamená 4; u C09 mentor potvrzuje návaznost na předchozí den | [Zdroj a implementace](backend.md#upřesnění-mentora-k-o10), komentáře předané uživatelem 17. 10. 2026. Jádro v7 a úzká offline návaznost předchozího dne implementované bez závislosti na léčbě/ID/reference. Skutečná regrese C08 → 3, C09 → 4. Snížený příjem s málem moči/závratí zůstává 3. Původní S4 zachovat; obecné řízení epizod a klinické převzetí zobecnění zůstává otevřené |
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
| Demo D1 · návaznost | Stávající `portal_controls` sdílejí pacient i lékař; ruční termín a volitelný interval, uložená historie plánu | Nález pouze ze zprávy se neztratí, ale nevymýšlí odpověď dotazníku. Odpověď obnoví jen výslovný interval; neodpověď se zobrazí bez změny klinické úrovně. Potvrzení není odeznění. S1 s. 5/9/12; S4 §4–6 |
| Demo D2 · lékařský pohled | Souhrn, kontext, doložené trendy a časová osa vznikají deterministicky ze stejných dostupných dat; podklady až v rozbalení | Bez nového LLM volání a zásahu do klinických pravidel. Změna naléhavosti není tvrzení o vyléčení; D1 je záznam cyklu, ne důkaz skutečného podání. S1 s. 5/12; S2 slidy 2–3/5; S7 / Zásady |
| Lékař | Stručná aktuální kartička, detail a LLM zpráva ze stejné revize | Nutný krok a zdroje viditelné bez čekání na LLM; starší zpráva je historická |
| M1 · přehled týmu | Kartička a `/team` jsou pohledy nad stejnými posledními hodnoceními; krátký souhrn tvoří šablona | Bez nové fronty a LLM; předání je označené jako simulované, neúplnost je oddělená od priority |
| M2 · měření a trendy | Export promítá vybrané validované vstupy stejného hodnocení; živý web přebírá trendy ze stávajícího adaptéru | Bez nového parseru, klinických prahů nebo registru léčby; rozporná měření zůstávají doložená, bez smyšleného bodu grafu. Nahrazené hodnoty zůstávají v intake |
| M4 · směrování | Čistý výpočet kontaktu a lhůty podle času hodnocení v Europe/Prague a pravidel §2/§5 | Po–Pá 7:00 včetně až 15:30 nezahrnuto; červená vždy 155, oranžová do 2 h nebo služba ihned, paliativní linka s náhradní pomocí. Nezmění klinickou úroveň, netvrdí doručení; svátky a výjimky pracoviště nejsou v dodaném kalendáři |
| M3 · obecný stav | Kladnou slovní odpověď upřesnit přes jedinou původní škálu; po skutečném potvrzení doložit vazbu `clarified_facts` | Bez odhadnutého čísla a bez globální výjimky prázdná fakta → zelená. Klinicky zpracovaný vstup bez otázky sám nevytváří neúplný sběr |
| M3 · paliativní kontext | Jen explicitní strukturovaný záměr „symptomatická paliativní péče“ se zdrojem; úrovně 2/3 mají 24h paliativní tým/hospic a záložní 155 podle S4 §5 | Červená se nesnižuje; neznámý telefon týmu se nevymýšlí. Přání jsou podklad pro zdravotníka k ověření platnosti, nikoli automatická výjimka z pomoci |
| Zastupování | Textové tlačítko „Nejste [jméno] a odpovídáte za pacienta? Klikněte zde.“ pod otázkou přepíná jedním kliknutím, včetně návratu; autor oddělený od subjektu potíží | Bez checkboxu a dalšího potvrzení volby. Oslovení skutečného adresáta; křestní jméno a doložený rod, jinak neutrálně; kanonický význam otázky zachovat |
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
