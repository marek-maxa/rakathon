# MEDDI ONCO Challenge

Tým zvolil tuto výzvu 16. 10. 2026. Cíl: funkční prototyp AI společníka,
který sleduje stav onkologického pacienta doma, zohlední léčbu a vývoj obtíží,
rozpozná riziko, doporučí další krok a připraví souhrn pro zdravotníka.
Zdroj: [zadání MEDDI](<../documents/MEDDI – MEDDI Onco.pdf>), s. 4–5.

Revize 17. 10. 2026: úplný [plán pipeline a webu](meddi-onco-plan.md)
zaznamenává požadavky, závislosti, komentáře týmu a kroky K0–K10 se zdroji
a přijímacími podmínkami. Tato etapa končí plánem, podle upřesnění týmu;
následným implementačním cílem je začlenění do existující větve `web`.

## Požadavky zadavatele

| Úroveň | Krok podle zadání |
| --- | --- |
| 1 · zelená | Další sledování |
| 2 · žlutá | Kontaktovat tým; odpověď do konce následujícího pracovního dne |
| 3 · oranžová | Telekonzultace do 2 hodin; mimo pracovní dobu sloužící lékař MOÚ |
| 4 · červená | Neodkladná pomoc: ihned 155 / urgentní příjem |

Zdroj: zadání MEDDI, s. 6. Toto je přepis provozního zadání, nikoli námi
ověřený klinický protokol. Konkrétní pravidla již dodává
[pravidla_triaze.md](../rakathon_meddi_onco_data/docs/pravidla_triaze.md), §1–6;
mentor má potvrdit jejich nejasné výklady a klinickou implementaci.

Řešení nestanovuje diagnózu ani nemění léčbu. Úrovně 2–4 končí u zdravotníka,
každé doporučení uvádí důvod a při pochybnosti se má eskalovat výše. Centrum
funguje Po–Pá 7:00–15:30, mimo tuto dobu zadání uvádí sloužícího lékaře MOÚ
nebo 155 (s. 7). Zpráva pacienta má přednost před dotazníkem, souhrn má být
čitelný do 30 sekund (s. 12). Interpretaci rozporů a přesné směrování potvrdí mentor.

## Data a ověření

Zadavatel slibuje JSON: 14 fiktivních pacientů, 171 záznamů, 4 dotazníky,
kontext léčby a léků, zprávy, měření, triážní pravidla a referenční souhrny
(s. 8). **Datový balíček je v [rakathon_meddi_onco_data/](../rakathon_meddi_onco_data/README.md).**
Lokálně ověřeno 14 pacientských JSON a 171 check-inů. README balíčku potvrzuje
fiktivní data a v oddílu 6 dovoluje pro tento prototyp libovolný jazykový model.
Obsahuje také triážní pravidla, definice dotazníků a oddělené reference.

Povinné situace (s. 9):

- Horečka v období poklesu bílých krvinek.
- Imunitní kolitida zhoršující se během dvou dnů.
- Plíživé známky srdečního selhání.
- Léková interakce a krvácení.
- Paliativní pacientka, za kterou píše dcera.
- Rozpor zprávy pacienta a dotazníku.

Hodnocení proběhne na 6 skrytých pacientech při přehrávání v čase. Řešení smí
vidět jen informace dostupné k danému okamžiku. Sleduje se záchyt oranžových
a červených situací i zbytečné poplachy; podhodnocení červené je nejzávažnější
chyba. Ručně se hodnotí srozumitelnost, vysvětlení a souhrn (s. 10).

Váhy: bezpečnost a klinický přínos 30 %, využitelnost 25 %, technologie a AI
20 %, UI 15 %, integrace 10 % (s. 11). Jde o soutěžní ověření na fiktivních
případech, nikoli o důkaz klinické účinnosti.

## Aktuální rozsah a hranice

JSON, samostatný intake a společný backend už existují. Zbývá úplný průchod
včetně `zprava_pacienta`, časové karty, poslední chemoterapie, sledování nálezů,
kontaktů a souhrnů. Kritický nález vyvolá okamžitou instrukci; na konci
dotazníku se triáž znovu vyhodnotí a uloží. Podrobnosti v aktuálním plánu.

Pro soutěž navrhujeme lokální demo a simulované předání upozornění.
Další implementace má využít existující web ve větvi `web`; jeho propojení
je samostatný milník před ostrým klinickým provozem. Hlas a trénování modelu
nejsou podmínkou základního toku. MEDDI API během akce nebude; integraci máme
navrhnout, hlas je bonus (s. 12). Ostrý provoz vyžaduje AWS v EU, ochranu dat
a provozní i klinické převzetí (s. 7; pacientská cesta / Provoz).

README balíčku, oddíl 4, definuje výstup na každý check-in a párování referencí.
S mentorem / organizátorem zbývá dořešit nejasnosti v interpretaci pravidel,
případné dodatečné hodnoticí rozhraní, termín a způsob odevzdání. Lokální PDF
termín neuvádí. Simulovaný čas a předem zaznamenané odpovědi zůstávají základem
opakovaného replay; odpovědi na nové otázky se nedoplňují z budoucnosti.

Doplňující [prezentace MEDDI](../documents/MEDDI_Onco_Rakathon_2026.pptx),
slidy 2–5, potvrzuje zaměření na koordinaci a kontext. Podrobné soutěžní
požadavky čerpáme z PDF; v relevantním rozsahu nebyl zjištěn rozpor.
