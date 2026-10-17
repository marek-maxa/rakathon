# Platná rozhodnutí

Požadavky a jejich zdroje jsou v [zadání](challenge.md), cílové chování
v [plánu](meddi-onco-plan.md), implementované rozhraní v [architektuře](architecture.md).
Tento dokument uchovává volby důležité pro další vývoj; historii implementačních
relací, mergů a testovacích běhů nahrazuje Git.

| Oblast | Rozhodnutí | Důvod / důsledek |
| --- | --- | --- |
| Stack | Python 3.12 + uv, stávající Flask/Jinja/Plotly | Rozšiřovat hotové prvky; nový frontend ani framework není podmínkou |
| Klinické rozhodování | Jediné deterministické jádro `meddi/`; kořenová API a web jsou adaptéry | Nekopírovat klinické prahy do UI nebo LLM |
| Role LLM | Extrakce, formulace cílených otázek a odborné zprávy z pevné předlohy | Úroveň, trendy, příjemce, termíny a akce určí kód; zpráva má šablonovou zálohu |
| Výstup | Oddělit zdrojový signál, minimum, výslednou úroveň a úplnost | Nevyřešený údaj není nula/false; relevantní nevyhodnocené vstupy mají lidskou cestu, známé 3/4 se nesnižuje |
| MASTER | Odpověď je obdobou `zprava_pacienta`, nikoli jiná klinická politika | Zachovat otázku, autora/časy; zpráva má při rozporu přednost podle pravidel §6.2/§6.4 |
| Potvrzení | Pacient kontroluje slovní návrhy; web používá společné potvrzení a opravy | Potvrzují se vyřešené odpovědi, nikoli automaticky všechny extrahované fakty |
| Karta | Události a revize zachovávají původ; aktuální karta je odvozený pohled | Oprava ani zlepšení nesmažou historii; nebrat maximum celé historie |
| Nálezy | Nezelené nálezy sledovat jako epizody; zahrnout relevantní zlepšení a kontext | Aktuální varovné příznaky pro 3/4 jsou podmnožina klíčových, u 1/2 prázdné |
| Kontroly | Jedna evidence pro cílené otázky i přeměření | Vazba na epizodu, priorita, termín, stav a deduplikace; intervaly schvaluje klinická politika |
| Lékař | Stručná aktuální kartička, detail a LLM zpráva ze stejné revize | Nutný krok a zdroje viditelné bez čekání na LLM; starší zpráva je historická |
| Zastupování | Nenápadná volba pod otázkou, autor oddělený od subjektu potíží | Oslovení skutečného adresáta; křestní jméno a doložený rod, jinak neutrálně; kanonický význam otázky zachovat |
| Léčba a čas | Poslední skutečné podání doložit; plán, D1 a typ cyklu rozlišovat | Neznámá léčba není negativní kontext, budoucí údaje nepatří do hodnocení |
| Úložiště | Zatím atomické JSON working copies pro jeden proces; originály neměnit | Trvalé události/resume a produkční databáze jsou další samostatný krok |
| Katalog | Explicitní katalog všech 49 otázek a zdrojové definice; zatím bez RAG | Podobnost není klinická jistota, tvrdá pravidla nesmějí záviset na top-k vyhledávání |
| Integrace | Datový a předávací adaptér oddělené od pravidel; MEDDI API během soutěže pouze navrhnout | SMTP demo není doručený klinický požadavek; ostrá data vyžadují ověřený EU provoz |
| Evaluace | Chronologický replay, reference a názvy scénářů mimo rozhodování/LLM | Nezávisle měřit záchyt i zbytečné eskalace; neladit pravidla podle ID nebo reference |

## Otevřený konflikt bezpečnostního výstupu

Dosavadní výslovný týmový pokyn skrývá výslednou triáž až do potvrzení a
úspěšného uložení, pro všechny barvy. Tak se chová současný formulář i jeho
regresní testy. Požadavek P07 a pravidla pořadatele §1–3 ale vyžadují
okamžitou reakci na kritický nález. Žádný z těchto bodů se pouhým úklidem
dokumentace nepovažuje za změněnou implementaci nebo odvolaný pokyn.

Návrh k rozhodnutí před K4: běžný závěrečný výsledek ponechat po potvrzení,
bezpečnostní instrukci pro známé kritické minimum oddělit a zobrazit před
pokračováním cíleného sběru. Na tuto instrukci nesmí mít vliv chyba ukládání,
dalšího LLM volání ani doručení zprávy týmu. Doporučení dořešit výslovně
v rámci K4; ostatní integrační práce mohou pokračovat.

Audit potvrdil, že `tests/test_survey_recovery.py` chrání čekání na potvrzení
i pro červenou a pokračování doptávání při známém červeném nálezu. Po přijetí
řešení K4 upravit odpovídající regresní očekávání; jejich současný průchod
není důkaz splnění P07. Ověřit také pořadí obecné extrakce, triáže a cíleného
LLM: změna samotného vykreslení až po návratu z `MasterDialogue` nestačí.

## Návrh úložiště k rozhodnutí v K2a

Doporučeným kandidátem pro lokální prototyp je SQLite ze standardní knihovny,
kvůli transakcím a unikátním klíčům bez další runtime závislosti. Není zatím
zvolena ani implementována. K2a musí konkretizovat malé úložné rozhraní
oddělené od Flasku, migraci současných pracovních kopií a ochranu původních dat.
Volba produkční databáze zůstává součástí K10 s MEDDI.
