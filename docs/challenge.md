# MEDDI ONCO Challenge

Tým zvolil tuto výzvu 16. 10. 2026. Cíl: funkční prototyp AI společníka,
který sleduje stav onkologického pacienta doma, zohlední léčbu a vývoj obtíží,
rozpozná riziko, doporučí další krok a připraví souhrn pro zdravotníka.
Zdroj: [zadání MEDDI](<../documents/MEDDI – MEDDI Onco.pdf>), s. 4–5.

## Požadavky zadavatele

| Úroveň | Krok podle zadání |
| --- | --- |
| 1 · zelená | Další sledování |
| 2 · žlutá | Kontaktovat tým; odpověď do konce následujícího pracovního dne |
| 3 · oranžová | Telekonzultace do 2 hodin; mimo pracovní dobu sloužící lékař MOÚ |
| 4 · červená | Neodkladná pomoc: ihned 155 / urgentní příjem |

Zdroj: zadání MEDDI, s. 6. Toto je přepis provozního zadání, nikoli námi
ověřený klinický protokol. Konkrétní rozhodovací pravidla potřebujeme od mentora.

Řešení nestanovuje diagnózu ani nemění léčbu. Úrovně 2–4 končí u zdravotníka,
každé doporučení uvádí důvod a při pochybnosti se má eskalovat výše. Centrum
funguje Po–Pá 7:00–15:30, mimo tuto dobu zadání uvádí sloužícího lékaře MOÚ
nebo 155 (s. 7). Zpráva pacienta má přednost před dotazníkem, souhrn má být
čitelný do 30 sekund (s. 12). Interpretaci rozporů a přesné směrování potvrdí mentor.

## Data a ověření

Zadavatel slibuje JSON: 14 fiktivních pacientů, 171 záznamů, 4 dotazníky,
kontext léčby a léků, zprávy, měření, triážní pravidla a referenční souhrny
(s. 8). **Datový balíček zatím v repu není.** Podmínky jeho sdílení a použití
externí AI je třeba potvrdit při převzetí.

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

## Náš první krok a hranice

Nejdříve otevřít dodaný JSON a společně popsat jeden případ v čase:
co přišlo, co už víme a co mají vidět pacient a zdravotník. Tento první průchod
nenahrazuje povinnost později pokrýt všech šest situací.

Pro první verzi navrhujeme lokální demo a simulované předání upozornění.
Hlas, ostré notifikace, produkční nasazení a trénování vlastního modelu
odkládáme. MEDDI API během akce nebude; integraci máme navrhnout, hlas je bonus
(s. 12). Konkrétní UI a AI službu teprve vybereme.

S mentorem / organizátorem zbývá potvrdit datový balíček, klinická pravidla,
hodnoticí vstup a výstup, termín a způsob odevzdání. Lokální PDF termín neuvádí.

Doplňující [prezentace MEDDI](../documents/MEDDI_Onco_Rakathon_2026.pptx),
slidy 2–5, potvrzuje zaměření na koordinaci a kontext. Podrobné soutěžní
požadavky čerpáme z PDF; v relevantním rozsahu nebyl zjištěn rozpor.
