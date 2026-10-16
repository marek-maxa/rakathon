# Technické řešení

Základ: Python 3.12 + uv, Linux / Windows PowerShell. Zatím jen pytest a Ruff.
Aplikace, datové schéma ani framework nejsou implementované nebo zvolené.

## Směr určený týmem

- První verze je CLI proof of concept. Prioritou jsou data, dotazování,
  vyhodnocování odpovědí a funkční průchod. Frontend, vizuál a nasazení odkládáme.
- Každý pacient má kartu aktuálního stavu zohledňující vývoj v čase. Karta
  poskytuje kontext dotazování a slouží také zdravotníkovi.
- LLM personalizuje otázky a interpretuje subjektivní odpovědi. Pomocí instrukcí
  a příkladů v kontextu je převádí do strukturovaných dat.
- Veškerou triáž provádí náš kód. LLM neurčuje ani nenavrhuje úroveň,
  doporučený krok, kontakt nebo upozornění týmu; potvrdil tým 16. 10. 2026.
- Systém reaguje na nové informace, plánuje další kontakt, poskytuje zpětnou
  vazbu a podle stavu upozorní tým. První CLI používá simulovaný čas a přehrávání
  událostí s předem zaznamenanými odpověďmi; potvrdil tým 16. 10. 2026.

## Rozdělení odpovědnosti

LLM převádí volný text na pozorování s vazbou na zdroj. Výstupní schéma
extrakce neobsahuje triážní rozhodnutí. Strukturované odpovědi dotazníků
a měření zpracovává přímo kód; není třeba je znovu interpretovat modelem.

Kód validuje pozorování, aktualizuje kartu a vyhodnocuje pravidla nad kontextem
léčby a historií. Pokrývá tvrdá pravidla i kontext, trendy, rozpory, chybějící
údaje a neodpovědi. Určí úroveň, další krok, kontakt podle pracovní doby
a upozornění týmu; vysvětlení odvodí ze spuštěných pravidel a jejich vstupů.
Převod kontextových pravidel do konkrétních podmínek zbývá upřesnit s mentorem.

Při dotazování kód určí potřebné informace a čas kontaktu, LLM personalizuje
formulaci. Nevalidní nebo nejasná extrakce je samostatný stav zpracování,
nikoli důkaz nízkého rizika. Postup při nejistotě a výpadku určí kód.

## Dostupný balíček a první režim

V [rakathon_meddi_onco_data/](../rakathon_meddi_onco_data/README.md) je lokálně
14 fiktivních pacientů a 171 check-inů (ověřeno načtením JSON 16. 10. 2026).
`pacienti/` jsou vstupy, `ground_truth/` jsou reference párované přes `checkin_id`.
Očekávaný výstup popisuje README balíčku, oddíl 4. To je první kontrakt našeho
vyhodnocení; případné dodatečné požadavky poroty zbývá potvrdit.

Návrh pro první CLI: přehrát zaznamenané události v jejich čase, vytvořit kartu,
vyhodnotit stav a zapsat návrh další otázky včetně důvodu a času kontaktu.
Historickou odpověď nepřiřazovat libovolné nově vygenerované otázce. Pokud nová
otázka nemá ve scénáři odpověď, ponechat ji otevřenou; nedoplňovat ji LLM
ani budoucím záznamem. Interaktivní rozhovor tím zatím není plně ověřen.

Z rozhodovacího kontextu vyloučit `nazev_scenare`, který není reálným vstupem
(README balíčku, oddíl 5), i veškeré reference. Časově filtrovat také laboratoř,
vyšetření, události týmu a změny léčby. U volných poznámek a výchozích souhrnů
nejprve ověřit, zda neprozrazují budoucí vývoj. Dostupnost výsledku nemusí být
totožná s časem odběru; význam časových polí je třeba dořešit při tvorbě adaptéru.

Pro prototyp nad smyšlenými daty organizátor povoluje libovolný LLM
(README balíčku, oddíl 6). Poskytovatele zatím nevybíráme. Klinická pravidla
bereme z dodaných podkladů; kvalifikované lidské ověření zůstává nutné.

## Zpřesnění k diskusi

**Historie a karta:** uchovat původní události, jejich autora, čas vzniku
i čas dostupnosti systému. Kartu chápat jako odvozený pohled, který lze obnovit
z historie; LLM navrhuje strukturovaná pozorování, nepřepisuje celou kartu.
U každého zjištění zachovat zdroj, čas a zda jde o výslovné sdělení, nebo odhad.
Chybějící údaj, popřený příznak a rozpor jsou různé stavy.

**Obsah a čas dotazu:** nejprve určit důvod kontaktu a potřebné informace
(pravidelná kontrola, upřesnění, sledování otevřeného problému). LLM navrhne
srozumitelnou formulaci. Časování, počet otázek, opakování a reakci na neodpověď
řídit explicitní politikou podle podkladů mentora. Nová spontánní zpráva musí
spustit vyhodnocení i mimo plánovaný kontakt. Známý urgentní signál nesmí čekat
na dokončení rozhovoru. Neodpověď sama nepotvrzuje stabilní zdravotní stav.

**Strukturovaná extrakce:** příklady v kontextu doplnit pevným schématem,
strukturou vynucenou API tam, kde je dostupná, a lokální validací. JSON
odpovídající schématu ještě nedokládá správné porozumění zprávě; kontrolovat
také vazbu na původní text, jednotky, čas a negace. Nevalidní výstup nebo výpadek
LLM nesmí potichu aktualizovat kartu ani být považován za úspěšné vyhodnocení.
Technický podklad: [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
ověřeno 16. 10. 2026; jde o příklad možnosti API, poskytovatele tím nevybíráme.

**Ověření:** zvlášť hodnotit extrakci, triáž a užitečnost dotazování. Historická
data ověří zpracování zaznamenaných zpráv, ale nemusejí obsahovat odpovědi
na nově vytvořené otázky. Pro interaktivní část připravit scénář s člověkem
nebo simulátorem; výsledek LLM simulace není nezávislá klinická reference.
Tým zvolil simulované hodiny a předem zaznamenané odpovědi. Adaptivní dotazování
proto zatím hodnotíme jako návrhy otázek, nikoli jako ověřený uzavřený rozhovor.

Otevřeno: konkrétní obsah karty, schéma extrakce a časovací politika.
Definice existujících dotazníků je v `rakathon_meddi_onco_data/docs/dotazniky_definice.json`.
Barvy odpovědí nejsou výsledná kontextová triáž (README balíčku, oddíl 4).
Tvrdá pravidla určují minimální úroveň; při rozporu se systém doptá a do té
doby počítá s horší variantou ([pravidla](../rakathon_meddi_onco_data/docs/pravidla_triaze.md),
oddíly 3 a 6). To jsou požadavky zadavatele, nikoli volitelná preference architektury.

## Návrh k společnému projití

Jeden lokální proces s oddělenými kroky zatím stačí. Nejprve ověříme tento tok
na jednom pacientovi; konkrétní soubory a rozhraní určíme podle dodaného JSON.

1. **Vstup a čas:** načíst kontext pacienta a události dostupné k okamžiku `t`.
   Oddělit reference pro hodnocení, aby neunikaly do rozhodování ani souhrnu.
2. **Porozumění zprávě:** spojit dotazník, měření a text s odkazy na původní
   záznamy. Zachovat čas, autora, chybějící údaje a rozpory. Zde může pomoci LLM.
3. **Triáž v kódu:** použít pravidla dodaná a potvrzená mentorem i dosavadní
   vývoj. Vrátit úroveň 1–4, důvody a podklady. LLM dodává pouze extrahovaná
   pozorování; triážní rozhodnutí vytváří výhradně kód.
4. **Výstup:** pacient dostane srozumitelný další krok, zdravotník prioritu
   a krátký souhrn s časovou osou. V demu předání upozornění simulujeme.
5. **Vyhodnocení:** přehrát stejné případy v čase a porovnat s oddělenými
   referencemi. Sledovat podhodnocení červené, záchyt oranžové/červené a počet
   zbytečných poplachů. Jednotku hodnocení a opakovaná upozornění vyjasnit
   podle hodnoticího rozhraní zadavatele.

Časové přehrávání a lidský dohled vyžaduje [zadání MEDDI](<../documents/MEDDI – MEDDI Onco.pdf>),
s. 7 a 10. Rozdělení komponent výše je náš návrh, ne předepsaná architektura.

## Co rozhodneme postupně

- Nad JSON: schéma událostí, dostupnost informací v čase, referenční výstup.
- Nad jedním případem: schéma extrakce, podmínky pravidel a chování při chybě
  a nejistotě. Rozdělení odpovědnosti LLM / triáž v kódu je již rozhodnuté.
- Po funkčním průchodu: jednoduché UI, ukládání stavu a způsob předvedení.
- Nakonec: popis budoucí integrace MEDDI. API na akci není (zadání, s. 12).

Externí AI služba zatím není vybraná ani zapojená. Pracujeme s dodanými
syntetickými daty a do budoucího LLM volání předáme jen potřebný kontext.

## Příkazy

Platí v Linuxu i Windows PowerShellu z kořene repozitáře:

```text
uv sync --locked
uv run ruff check .
uv run pytest
```

`pytest` zatím nemá co spustit a skončí kódem 5 (žádné testy).
Příkaz aplikace a smysluplné testy doplníme s prvním implementačním krokem.
