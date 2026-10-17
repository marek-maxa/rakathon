# Plán pipeline a webu

Tento dokument určuje cílové chování a přijímací podmínky dalšího vývoje.
[Zadání](challenge.md) obsahuje zdrojované požadavky P01–P27;
[architektura](architecture.md) popisuje implementaci a její mezery;
[úkoly](tasks.md) určují otevřenou práci. Navržené záznamy níže nejsou hotové API.
Rozvíjet existující Flask, intake, pravidla, export a report po malých krocích.

## Cílový tok

1. Pacient otevře svůj profil a dostane širokou MASTER otázku. Pod otázkou
   může uvést, že odpovídá za pacienta. Odpověď má roli `zprava_pacienta`.
2. Uloží se původní událost s autorem a časy ještě před LLM. Z karty se sestaví
   kontext dostupný v okamžiku hodnocení, včetně posledního skutečného podání léčby.
3. Obecná extrakce získá fakta i nové potíže zmíněné při cílené otázce.
   Deterministický backend ověří vstupy, známé riziko a nejistotu před dalším
   cíleným LLM voláním. Kritický krok nesmí čekat na dokončení rozhovoru.
4. Systém doplní jen potřebné údaje a vyžádá potvrzení. Zachová rozdíl mezi
   původním sdělením, návrhem odpovědi, potvrzeným údajem a nevyřešeným vstupem.
   Prázdná zpráva nebo neodpověď nejsou popření příznaků.
5. Po potvrzení, přerušení či opravě vznikne odpovídající uložená revize triáže.
   Dokončení sběru neznamená automaticky úplné klinické posouzení.
6. Aktualizuje se karta, klíčové/varovné nálezy a pacientské doporučení.
   Podle pravidel vznikne evidovaný požadavek týmu s prioritou a lhůtou.
7. Otevřené epizody vytvoří nebo aktualizují kontroly: cílenou otázku či
   přeměření. Již známá odpověď kontrolu splní bez zbytečného opakování.
8. Časový podnět zpracuje splatné/nezodpovězené kontroly i bez otevření reportu.
   Odpověď či měření se vrátí do stejného toku; nové vyhodnocení upraví sledování.
9. Při eskalaci, před kontrolou/podáním nebo ve schváleném intervalu kód
   připraví stručnou kartičku pro lékaře. LLM pouze formuluje zprávu ze stejných
   hotových dat. Zásah zdravotníka se uloží a promítne do dalšího sledování.

Obsluhu události a běh v čase řídí jedna aplikační služba. Samotný plánovač
neklasifikuje potíže. LLM neurčuje triáž, příjemce, prioritu ani termín kontroly.
Pořadí dotazů: relevantní bezpečnostní upřesnění → rozpor/nová nebo horší potíž
→ splatná kontrola → potřebné rutinní údaje. Známá urgentní akce již není
podmíněna další odpovědí. Rozpočet dotazů nesnižuje známé riziko.

## Pacientská karta a zdrojové události

| Záznam | Potřebný obsah |
| --- | --- |
| Událost | Stabilní ID, pacient/kontakt, původní text nebo měření, zdroj, autor, skutečná otázka, čas pozorování a dostupnosti, vazba na opravu |
| Pozorování | Pojem, hodnota/interval, jednotka a časové okno, subjekt, přítomnost/popření/nejistota, citace a zdrojová událost, potvrzení |
| Léčebný kontext | Druh léčby, platnost léků, skutečná a plánovaná podání zvlášť, poslední chemoterapie a odstup, cyklus, zdroje a chybějící údaje |
| Nález / epizoda | Stabilní ID, první/poslední pozorování, aktuální stav a trend, zdrojová barva odděleně od klinické úrovně, aktivovaná pravidla, důkazy, otevření/zlepšení/odeznění |
| Revize triáže | Pacient/kontakt/check-in, čas, revize vstupů a pravidel, celý intake a zmrazené vstupy, minimum/úroveň/úplnost, důvody a výstupní krok |
| Kontrola | Vazba na nález/epizodu, co a proč ověřit, priorita, typ otázka/přeměření, termín nebo potřeba plánování týmem, verze politiky, stav a splňující událost |
| Předání | Hodnocení/revize, priorita, příjemce, lhůta, stav odeslání a převzetí, pokusy a klíč proti duplicitám |
| Snapshot | Aktuální pohled k `as_of`, revize, relevantní pozorování, léčba, otevřené epizody a kontroly; rekonstruovatelný z historie |

Událost, její odvozená fakta a export nejsou tři nezávislá hlášení téže věci.
Opravy a nové revize zachovají původ; opakovaný POST/import nesmí vytvořit
nový nález či alert. Stabilní identifikátor odeslání musí přežít opakovaný
POST i obnovení klienta; kontrola duplicit až podle exportovaného `checkin_id`
nestačí, pokud opakování založí novou zdrojovou událost. Událost uložit před
LLM a výsledek externího zpracování připojit k odpovídající revizi vstupů.
Při chybě zápisu nepotvrdit úspěšné přijetí; již známou kritickou instrukci
neskrýt kvůli chybě dalšího ukládání nebo zpracování.

Při změně úložiště zavést adaptér a migraci současných pracovních kopií.
SQLite ze standardní knihovny je doporučený kandidát pro lokální prototyp
kvůli transakcím a unikátním klíčům; volbu a migraci konkretizovat v K2a.
Nejde o přijaté rozhodnutí o lokální ani produkční databázi.
Snapshot dialogu sám není implementované resume: uložit a obnovit také
rozpracovaný stav, návrhy, potvrzení, závislosti a rozpočet dotazů,
bez opakování již dokončených LLM volání. Neukládat klienta ani jeho tajemství.

Čas hodnocení předávat explicitně; časy ukládat s pásmem, zobrazovat a
směrovat v `Europe/Prague`, nezávisle na lokálním pásmu serveru.
U původních dat bez pásma/času zachovat originál a explicitní převodní politiku.
Dostupnost výsledku laboratoře není automaticky čas odběru. Filtrovat i léčiva,
podání, vyšetření, poznámky a zásahy týmu; budoucí změna v souhrnném poli
nesmí proniknout do dnešního rozhodování. Platnost ani klinickou expiraci
nevymýšlet univerzálně podle stáří záznamu (S3 §4–5, S4 §5–6).

## Klíčové nálezy a doporučení

Všechny nezelené odpovědi a klinické nálezy vstupují mezi klíčové; také
významná zlepšení a relevantní kontext. Není to jen výběr nejhorších barev.
Uchovat zdrojovou barvu, závažnost nálezu a jeho vliv na celkovou triáž zvlášť.

Aktuální nález nebo kombinace vedoucí podle pravidel k 3/4 tvoří podmnožinu
`varovne_priznaky`. U 1/2 je prázdná. Odeznělý varovný příznak zůstává důležitým
klíčovým nálezem, ale není současným varováním. Nejistá riziková alternativa
se nevydává za potvrzený příznak. Oba seznamy mají odkazovat na stejné nálezy,
nikoli vznikat nezávislým textovým generováním.

Doporučení vybírá kód z klíčových nálezů, výsledné úrovně a odpovídajících
pravidel/plánu i u zelené a žluté. Nespojovat bez kontextu všechna upozornění
možností. Převzetí upozornění týmem samo nesnižuje závažnost; zlepšení se musí
doložit aktuálními údaji a nový nebo horší příznak posoudit znovu.
Zdroj: týmový výklad, S4 §1 a §3–6, S7.

## Zpráva pacienta a personalizace

Odpověď na MASTER má stejnou klinickou cestu jako původní `zprava_pacienta`.
`source=master_question` zachová skutečnou otázku; původní zpráva bez známé
otázky má `source=patient_message`, `question=null`. Nová cílená odpověď má
vlastní událost a původní text otázky. Cílový export uchová úvodní volné
sdělení v `zprava_pacienta`, ostatní odpovědi zvlášť uvnitř kontaktu.
Při rozporu s dotazníkem se systém doptá a do vyřešení počítá s horší
podloženou variantou (S4 §6.2/§6.4). Ani příloha není automatická diagnóza;
nevyhodnotitelný podklad zůstává k posouzení.

Pod otázkou zobrazit přístupný nenápadný checkbox, např.
„Odpovídám za [jméno pacienta]“. Volitelně doplnit jméno/vztah pečující osoby.
Zvolený pacient zůstává viditelný. Autor se uloží u každé události a správně
do `vyplnil`; změna během kontaktu nepřepíše starší autory. Pro původní data
použít jejich `vyplnil`. Volba zastupování není oprávnění k cizí kartě.

Autor odpovědi a subjekt obtíží jsou různé údaje. Při odpovídání dcery
zůstává hodnocenou osobou pacientka; vlastní vyčerpání dcery má samostatný
nález. Oslovovat skutečného adresáta: např. pacientce „Jak se dnes cítíte,
Hano?“, pečujícímu „Jak se dnes cítí Hana?“ (S4 §6.7 a §4).

Použít křestní jméno, vykání a doložený rod/preferované oslovení. Při neznámých
údajích neutrální formulaci, rod neodhadovat jen ze jména. Pro samotné jméno
není potřeba další LLM volání; úvodní otázku může formulovat šablona,
existující LLM doptání dostane jen potřebný kontext oslovení. Uložit kanonické
ID/metadata i skutečně zobrazené znění. Personalizace nesmí změnit možnosti,
jednotky, časové okno ani klinické mapování otázky.

## Rozhraní lékaře a souhrn

Rozšířit existující report, případně přidat pracovní přehled prioritních
požadavků ve stejné Flask aplikaci. Oprávněný lékař vidí stručnou kartičku
a může přejít do detailu pacienta.

| Stručná kartička | Detailní karta |
| --- | --- |
| Pacient, `as_of`, stáří údajů a revize | Časová osa kontaktů a původní zdroje |
| Aktuální úroveň, důvody, varovné příznaky, zásadní trend a nejistoty | Úplná historie relevantních nálezů, zlepšení, epizod a rozporů |
| Nutný krok, odpovědná role/osoba, termín, stav předání/převzetí | Léčba a poslední podání, relevantní léky, laboratoře, vyšetření a zásahy |
| Nejbližší kontroly a autor poslední odpovědi | Kontroly, měření, grafy, doručení, autoři a revize hodnocení |

Kód sestaví pevnou datovou předlohu kartičky se zdrojovými ID a časy.
LLM z těchto hotových dat pouze formuluje krátkou zprávu; nesmí vybírat jiné
klinické závěry z nevybraného detailu, dopočítávat trendy, měnit úroveň,
příjemce či termín nebo přidávat diagnózu/dávkování. Detail zpřístupní důkazy.

Kartička i zpráva nesou stejnou revizi a `as_of`. Po novém vstupu se kartička
aktualizuje; starší LLM text je historický, dokud nevznikne nový. Strukturu,
pevná pole a vazby tvrzení na fakta validovat; validní JSON sám nezaručuje
správný význam. Při chybě/limitu LLM použít deterministickou šablonu.
Aktualizace stavu a urgentní předání na generování textu nečekají.
Formát a čitelnost do 30 sekund ověřit podle S7, nikoli jen počtem znaků.

## Společný plán otázek a přeměření

| Typ kontroly | Co získává | Splnění |
| --- | --- | --- |
| Cílená otázka | Průběh příznaku, chybějící podmínku pravidla nebo účinek doloženého postupu; využije existující cílený intake a obecnou extrakci nových potíží | Relevantní potvrzená odpověď nebo explicitní dořešení týmem |
| Přeměření | Konkrétní parametr, hodnotu, jednotku, čas a zdroj; vazba na původní měření | Nové platné odpovídající měření, nikoli pouhé otevření upozornění |

Každá kontrola má důvod, vazbu na epizodu, prioritu, čas nebo stav „termín určí
tým“, verzi politiky a historii oznámení. Rozlišit čekající, splatnou,
oznámenou, splněnou, opožděnou, zrušenou či nahrazenou kontrolu. Deduplikovat
otevřené úkoly; odpověď z jiného kontaktu je může splnit.

Nezelené nálezy sledovat, prioritně ty, které zhoršily celkový stav.
Bezprostřední akce, rychlé upřesnění nejistoty a následné sledování jsou
různé priority. Přeměření neodkládá již doloženou urgentní pomoc.
Výstupní lhůta úrovně není automaticky interval měření. Intervaly,
opakování a podmínky uzavření musí být podložené schválenou politikou;
zdroj neudává úplný protokol pro všechny parametry. Neodpověď není zlepšení.
Zdroj: S4 §2–6; týmový požadavek cílených kontrol a přeměření.

## Implementační kroky a závislosti

| Krok | Závislost a rozsah | Podmínka dokončení |
| --- | --- | --- |
| K1 · webový základ | Existující Flask, MASTER, doptání, kontrola a opravy | Funkční průchod a API ověřené náhradou LLM; základ již existuje |
| K2a · trvalé přijetí události | K1; úložné rozhraní nad working copies, volba úložiště a migrace, stabilní ID kontaktu/odeslání, původní vstup před LLM | Přijatý originál včetně autora, skutečné otázky, časů a vazby opravy přežije timeout i restart; opakovaný POST nevytvoří druhou událost; chyba zápisu není úspěšné přijetí |
| K2b · obnova dialogu a revize | K2a; serializovaný stav dialogu a uložené výsledky zpracování, průběžné/konečné/přerušené revize | Po restartu pokračování ve stejném bodě bez opakování dokončených LLM volání; zachované návrhy, potvrzení, opravy, nejistota i auditní původ |
| K2c · měření a export | K2a/K2b; jednotná zdrojovaná měření a adaptér původního formátu | Stejné měření v triáži, historii i grafu; správný autor, MASTER oddělený od cílených odpovědí, opravy a deduplikace |
| K3 · časový kontext a podání | K2; využít `patient_inputs`, registry a odvozené trendy | Skutečné podání oddělené od plánu/typu cyklu, doložený odstup; snapshot bez budoucích dat, včetně potřebných historických souvislostí pro živý web |
| K4 · orchestrace a bezpečnost | K2/K3; společná aplikační služba a bod před další cílenou extrakcí | Známé riziko nečeká na konec; závěr/přerušení uloží revizi; chyba LLM nebo zápisu neztratí zdroj a nevytvoří zelený úspěch; vyřešený konflikt UI |
| K5 · nálezy a kontroly | K2–K4 a schválené časování | Aktivní epizody, klíčové/varovné vazby, zlepšení, otázky i přeměření, splnění/nezodpovězení a opakovatelný běh v čase bez duplicit |
| K6 · doporučení, předání a souhrn | První průchod po K3/K4, dokončení po K5; využít `disposition`, předávací adaptér a pevnou předlohu | Zdůvodněný krok a skutečná lhůta; 2–4 mají dohledatelné předání/převzetí a opakování při chybě; LLM pouze formuluje, existuje šablonová záloha |
| K7 · text a klinické pokrytí | Průběžně K2–K6; mentor a otevřené otázky backendu | MASTER i importované zprávy stejnou klinickou cestou; intervaly/rozpory/nepokryté pojmy nemizí; nezvyšovat počet zelených ukrýváním nevyhodnocených vstupů |
| K8 · pacient a zdravotník | První kartička společně se základem K6 po K3/K4, dokončení K1–K7; rozšířit Flask/Jinja a report | Aktuální kartička, detail a zpráva stejné revize, kontroly a nutné kroky; role, převzetí a zásah týmu; checkbox zastupování a správné oslovení bez změny významu otázky |
| K9 · průběžný replay a demo | Kontroly od K2, celý tok po K4–K8 | Všech 171 check-inů a šest povinných situací, negativní/mezní případy, metriky záchytu i falešných eskalací, srozumitelnost a záložní demo bez API |
| K10 · MEDDI/AWS | K9; pracoviště a provozní převzetí | Návrh adaptérů, EU cesta dat/LLM, identita, tajemství, audit, obnova, selhání a odpovědný tým; skutečné nasazení je samostatný milník |

K2 je souhrn K2a–K2c; první implementační změnou má být K2a. Rozsah navazovat
po malých samostatně ověřitelných krocích, poté propojit K3/K4. Audit nadměrných
eskalací a klinických mezer K7 probíhá při rozšiřování se stávajícím vlastníkem.
K9 začíná kontrolou každého kroku; celý replay nesmí být až posledním místem,
kde se ověří propojení komponent.

Po K3/K4 vytvořit první průchod K6/K8: trvalý požadavek týmu, příjemce,
priorita, vypočtený termín, opakování a převzetí spolu s jednoduchou kartičkou
ze stejné revize. Může používat doložené důvody současného hodnocení; úplné
epizody a plánovač K5 ani LLM souhrn nejsou podmínkou tohoto průchodu.
Simulované doručení viditelně označit; pro sdílený přístup zajistit oprávnění.
Následně dokončit K5 a zbývající K6/K8. Toto pořadí upřednostňuje bezpečnost
a využitelnost (S1 s. 10–12; S2 slidy 2–3 a 5), nemění klinické prahy.

Přehled aktuálních stavů/vlastníků je pouze v [tasks.md](tasks.md). Úložiště,
nové soubory či služby nejprve konkretizovat v příslušném malém kroku;
tento plán sám nezakládá větve ani nové moduly a neřeší otevřený konflikt K4.

Vazby: K2 → P03/P08/P20/P21; K3 → P02/P27; K4 → P05–P08/P15;
K5 → P01/P09/P10/P16/P17; K6 → P11–P14/P18/P19/P23;
K7 → P04–P06/P15/P16; K8 → P17/P19/P26; K9 → P21/P22/P25;
K10 → P12/P23/P24.

## Ověření a otevřené závislosti

Před každou změnou určit cíl, rozsah souborů a pozorovatelnou podmínku
dokončení. Vedle vhodných regresních testů ověřit integrační chování daného
kroku: restart, opakované odeslání, opravu, timeout/neplatný výstup LLM a chybu
zápisu. Kontrola předchozího stavu dialogu sama neprokazuje zachování nového
vstupu. Pro časový kontext ověřit, že přidání budoucího záznamu nezmění starší
hodnocení. U bezpečnostního bodu sledovat také pořadí volání: známé riziko
vyhodnotit před cíleným LLM, nejen zkontrolovat konečnou barvu.

Vedle šesti povinných situací podle [zadání](challenge.md#data-a-ověření)
ověřit zejména:

- Ekvivalentní MASTER a importovaný text při stejném kontextu/čase → stejná
  triáž; rozpor proti dotazníku zůstane k doptání s horší podloženou variantou.
- Nový kritický příznak při otázce na něco jiného, chyba cíleného LLM,
  omezený rozpočet, přerušení a selhání zápisu neztratí známé riziko.
- Zlepšení po zásahu neudržuje navždy starou červenou; nové obtíže se nepřehlédnou
  kvůli převzetí staršího požadavku. Žlutý nález je klíčový, nikoli aktuální varovný.
- Pacient/pečující, změna autora, neznámé jméno/rod, negace a personalizace
  nemění subjekt ani výsledek stejné odpovědi. Kontrolovat i skutečnou otázku
  pro krátké „ano/ne“ a kanonické metadata pro časová okna.
- Hranice pravidel a zdrojové rozpory: 42 dnů, nadir, teplota/saturace, přesně
  7 stolic nad normál, interval 5–6 zvracení, NRS 0, jednotky a true/false/unknown;
  očekávání určit podle zdroje a schváleného výkladu, nikoli podle ID pacienta.
- Přeměření doplní správný parametr a splní správný úkol; opakovaný podnět,
  POST nebo doručení nevytvoří duplicitní nález/kontrolu/upozornění.
- Pracovní doba, víkend, změna pásma, zvláštní lhůty, nedostupný příjemce,
  selhání/obnovení a oddělení doručení od převzetí.
- Kartička/detail/LLM zpráva stejné revize a zdrojů; starší text je označený,
  chybový souhrn má zálohu, jiný pacient nevidí cizí kartu.

Reference se čtou až v evaluaci. Nové otázky bez historické odpovědi zůstanou
otevřené; nevyplňovat je budoucím záznamem nebo referencí. Odděleně měřit
strukturovaný backend, extrakci a celý tok: red/orange záchyt, podhodnocení,
vyšší výsledky, neúplnost, správné kontakty/doručení, počet a zbytečnost otázek,
latenci, chyby a tokeny bez citlivého textu v logu. Pacientské potvrzení není
nezávislé ověření přesnosti modelu.

Rozdíly proti referencím třídit podle příčiny: chybějící vstup, chyba extrakce,
nepokryté mapování, chybějící trend nebo sporný klinický výklad. Vyšší výsledek
není automaticky zbytečná eskalace a příznak `requires_review` není počet
klinických poplachů. Zlepšení shody nesmí vzniknout odstraněním nevyhodnocených
zpráv či měření. Výchozí omezení a stav replaye jsou v
[architektuře](architecture.md#výchozí-stav-pro-k2); klinické výklady potvrzuje mentor.

Klinické závislosti O1–O10 jsou pouze v [backendu](backend.md#otevřené-klinické-otázky).
Konflikt bezpečnostního výstupu je v [rozhodnutích](decisions.md#otevřený-konflikt-bezpečnostního-výstupu).
Termíny přeměření, kontakty a kalendář potřebují souhlas příslušného odborníka
či pracoviště; obecné technické práce tím nejsou zablokované.

## Integrace a provoz

Podle S6 oddělit datový a předávací adaptér od rozhodování. Potřebné operace:
načíst kontext k času, přijmout zprávu/check-in/měření, uložit revizi a souhrn,
vytvořit prioritní požadavek, odeslat pacientovi instrukci a přijmout zásah týmu.
Názvy MEDDI endpointů zadání neurčuje. Pro demo lze předání simulovat a viditelně
odlišit od skutečného doručení; pevný testovací e-mail není klinická integrace.

Návrh cílového provozu: web a služba v AWS EU, neveřejné úložiště, správa
rolí/tajemství, audit, záloha/obnova a spolehlivá fronta předání s opakováním.
Konkrétní databázi, služby a autentizaci zvolit s MEDDI. Pro ostrá data ověřit
EU cestu včetně modelu, logů a záloh a podmínku neukládání u třetích stran.
Povolení libovolného modelu platí pro syntetický soutěžní balíček (S3 §6.9; S6).
