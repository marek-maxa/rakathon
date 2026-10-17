# Zadání MEDDI ONCO

Cíl: funkční prototyp podpory onkologického pacienta doma, který zjišťuje
obtíže a jejich vývoj, používá dostupný kontext léčby, rozpozná riziko,
doporučí další krok a předá zdravotníkovi přehled se zdroji.

## Zdroje a jejich platnost

| ID | Zdroj | Rozhodující části |
| --- | --- | --- |
| S1 | [Zadání MEDDI](<../documents/MEDDI – MEDDI Onco.pdf>) | Cíle s. 4–5, úrovně s. 6, mantinely s. 7, data s. 8, situace s. 9, evaluace s. 10–11, souhrny a integrace s. 12 |
| S2 | [Prezentace](../documents/MEDDI_Onco_Rakathon_2026.pptx) | Koordinace, odpovědnost a kontext, slidy 2–3 a 5 |
| S3 | [README datového balíčku](../rakathon_meddi_onco_data/README.md) | Vstupy a výstupy §4–5, podmínky použití a bezpečnost §6 |
| S4 | [Pravidla triáže](../rakathon_meddi_onco_data/docs/pravidla_triaze.md) | Úrovně a kontakty §1–2, tvrdá minima §3, typické situace §4, kontext a obecná pravidla §5–6 |
| S5 | [Definice dotazníků](../rakathon_meddi_onco_data/docs/dotazniky_definice.json) | Přesné otázky, možnosti, podmínky a směr škál |
| S6 | [Pacientská cesta](../rakathon_meddi_onco_data/docs/pacientska_cesta_meddi_onco.md) | Napojení řešení, technická integrace a provoz |
| S7 | [Vzorové souhrny](../rakathon_meddi_onco_data/docs/vzorove_souhrny_pro_lekare.md) | Zásady a čtyři ukázky zpráv pro odborníka |

Pořadatel určuje soutěžní a klinické požadavky. Týmové doplnění toku a UI je
v [plánu](meddi-onco-plan.md), význam výstupních polí také v [AGENTS.md](../AGENTS.md).
Klinické nejasnosti musí potvrdit kvalifikovaný člověk; evidují se
v [backendu](backend.md#otevřené-klinické-otázky). Původní podklady neměnit.

## Požadavky a přijímací podmínky

ID P01–P27 propojují zadání s implementačními kroky K1–K10 v plánu.
Tabulka vyjadřuje požadovaný výsledek, nikoli tvrzení o hotové implementaci.

| ID | Požadavek | Zdroj |
| --- | --- | --- |
| P01 | Pravidelně a srozumitelně zjistit symptomy, intenzitu a vývoj; neopakovat známé údaje a omezit zátěž pacienta | S1 s. 5; S3 §2; tým |
| P02 | Použít časově dostupnou léčbu, léky, komorbidity, výchozí stav, laboratoře, vyšetření a zásahy týmu | S1 s. 5, 8; S3 §5; S4 §5–6 |
| P03 | Zachovat dotazníky, zprávu pacienta, měření a přílohy s dohledatelným původem | S1 s. 8; S3 §5; S6 |
| P04 | Zpracovat češtinu, slovenštinu, překlepy a text bez diakritiky; uchovat originál | S1 s. 8; S3 §5 |
| P05 | Zprávu vyhodnotit i bez odpovídající volby v dotazníku; rozpor doptat a do vyřešení počítat s horší podloženou variantou | S1 s. 12; S4 §6.2–4 |
| P06 | Jediné deterministické jádro určí úroveň 1–4; výsledek neklesne pod aktivované tvrdé minimum | S4 úvod a §3; tým |
| P07 | Známý kritický nález vyvolá okamžitou instrukci a upozornění; nečeká na potvrzení či konec dotazníku | S1 s. 6–7; S4 §1–3; tým |
| P08 | Konec kontaktu vyvolá nové hodnocení a uloženou revizi s podklady; rozpracovaný či přerušený stav je samostatný | S3 §4; tým |
| P09 | Nezelené odpovědi i klinické nálezy evidovat jako klíčové a sledovat; zaznamenat také důležitá zlepšení a kontext | S4 §4–6; S7; tým |
| P10 | Aktuální varovné příznaky vedoucí k 3/4 jsou podmnožina klíčových; u 1/2 je seznam varovných prázdný | S4 §1, §3–4; týmový výklad |
| P11 | Doporučení vychází z klíčových nálezů, úrovně a pravidel i u 1/2; obsahuje důvod, konkrétní krok a kontakt | S1 s. 6–7, 12; S3 §4–6; tým |
| P12 | Úrovně 2–4 předat zdravotníkovi se správnou prioritou, lhůtou a evidencí doručení/převzetí | S1 s. 7; S4 §1–2; S6 |
| P13 | Kontakty a lhůty řídit pracovní dobou a časem Europe/Prague; červená vždy ihned | S1 s. 6–7; S4 §2 |
| P14 | Nesdělovat pacientovi diagnózu a neměnit léčbu či dávky; připomenout jen doložený předem určený lékařský postup | S3 §6.1; S4 §6.5 |
| P15 | Nejasnost, neodpověď, chyba modelu a chybějící údaj nejsou negativní nález; zachovat riziko a lidské posouzení | S3 §6.2; S4 §4, §6.4 |
| P16 | Hodnotit aktuální epizodu a trend; zlepšení po zásahu zachovat, nové/zhoršené obtíže posoudit znovu | S4 §5, §6.1, §6.3 |
| P17 | Při zastupování oslovit pečujícího, oddělit jeho potíže od pacientových a hodnotit jeho zátěž | S3 §5; S4 §4, §6.7 |
| P18 | Paliativní přání předat týmu; nevyloučit jimi pomoc a zajistit náhradní kontaktní cestu | S4 §5 |
| P19 | Souhrn pro lékaře do 30 sekund: aktuální důvod, očekávaný krok, relevantní kontext, trendy, zdroje a nejistoty | S1 s. 12; S7 |
| P20 | Každý check-in má strukturovaný výstup a správné patient_id/checkin_id; neúplný kontakt se nevydává za úplné posouzení | S3 §4–5 |
| P21 | Replay i LLM vidí jen informace známé do hodnoceného okamžiku; žádné reference, názvy scénářů ani budoucí souhrny | S1 s. 10; S3 §4–5 |
| P22 | Ověřit šest povinných situací i negativní a hraniční případy | S1 s. 9–10 |
| P23 | Oddělit datový adaptér od logiky a navrhnout napojení MEDDI bez dostupného API | S1 s. 12; S6 |
| P24 | Pro ostrý provoz zajistit AWS a data v EU, bez ukládání u třetích stran; do LLM pouze nezbytná data | S1 s. 7; S3 §6.9; S6 / Provoz |
| P25 | Měřit záchyt oranžových/červených, podhodnocení a zbytečné eskalace, správné kontakty a srozumitelnost | S1 s. 10–11; S3 §4 |
| P26 | Využít existující web a stejné backendové API/pravidla jako CLI | tým |
| P27 | Evidovat poslední skutečnou chemoterapii, odstup, druh léčby a zdroj; cyklus ani plán samy nejsou důkaz podání | S3 §5; S4 §3, §5; tým |

## Kontakty a lhůty

Přepis S4 §1–2; nejde o nové klinické prahy.

| Úroveň | Krok | Kontakt a lhůta |
| --- | --- | --- |
| 1 · zelená | `dalsi_sledovani` | Další sledování a instrukce, kdy se ozvat dříve |
| 2 · žlutá | `kontaktovat_tym` | Centrum; vyřízení do konce následujícího pracovního dne, mimo pracovní dobu následující pracovní den |
| 3 · oranžová | `telekonzultace` | V pracovní době lékař MOÚ do 2 hodin, mimo ni sloužící lékař MOÚ ihned |
| 4 · červená | `neodkladna_pomoc` | Ihned 155 / urgentní příjem; podle §2 tým upozornit do 15 minut |

Centrum pracuje v pracovní dny 7:00–15:30. S4 uvádí službu MOÚ 724 590 848.
Pro reálný provoz kontakty a kalendář potvrdí pracoviště. S4 §4 navíc stanovuje
zvláštní lhůty, například před další dávkou léčby nebo ještě tentýž den;
obecná žlutá lhůta je nenahrazuje. Paliativní kontakt a náhradní pomoc řídí S4 §5.

## Data a ověření

Balíček obsahuje 14 syntetických pacientů, 171 check-inů a čtyři dotazníky
se 49 otázkami (S1 s. 8; S3 §1–4; S5). Barva jednotlivé odpovědi není výsledná
triáž: nezná léčbu, trend ani volný text (S3 §4 / Dotazníky).

Povinné situace podle S1 s. 9:

- Horečka v období poklesu bílých krvinek.
- Imunitní kolitida zhoršující se během dvou dnů.
- Plíživé známky srdečního selhání.
- Léková interakce a krvácení.
- Paliativní pacientka, za kterou píše dcera.
- Zpráva pacienta odporující dotazníku.

Hodnocení používá šest skrytých pacientů a chronologické přehrávání;
podhodnocení červené je nejzávažnější chyba. Váhy: bezpečnost 30 %, využitelnost
25 %, technologie/AI 20 %, UI 15 %, integrace 10 % (S1 s. 10–11).

## Hranice prototypu

Prototyp stavíme nad syntetickými daty. MEDDI API během soutěže není dostupné;
požaduje se návrh adaptéru. Hlas je bonus (S1 s. 12). Ostrý provoz vyžaduje
klinické a provozní převzetí, role, obnovu a ověřenou EU cestu dat (S1 s. 7; S6).

Termín, formát odevzdání a případné dodatečné hodnoticí rozhraní nejsou
v dostupném zadání určeny; ověřit s pořadateli. Podklady odkazované mimo
repozitář, například původní e-mail či produktový leták, nevytvářejí nové
ověřené požadavky. Implementovaný stav je v [architektuře](architecture.md),
cílový tok a závislosti v [plánu](meddi-onco-plan.md).
