# Technické řešení

Základ: Python 3.12 + uv, Linux / Windows PowerShell. Zatím jen pytest a Ruff.
Aplikace, datové schéma ani framework nejsou implementované nebo zvolené.

## Návrh k společnému projití

Jeden lokální proces s oddělenými kroky zatím stačí. Nejprve ověříme tento tok
na jednom pacientovi; konkrétní soubory a rozhraní určíme podle dodaného JSON.

1. **Vstup a čas:** načíst kontext pacienta a události dostupné k okamžiku `t`.
   Oddělit reference pro hodnocení, aby neunikaly do rozhodování ani souhrnu.
2. **Porozumění zprávě:** spojit dotazník, měření a text s odkazy na původní
   záznamy. Zachovat čas, autora, chybějící údaje a rozpory. Zde může pomoci LLM.
3. **Triáž:** použít pravidla dodaná a potvrzená mentorem i dosavadní vývoj.
   Vrátit úroveň 1–4, důvody a podklady. Návrh: explicitní bezpečnostní pravidla
   mají přednost před výstupem LLM; podrobnosti domluvíme nad daty.
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
- Nad jedním případem: hranice pravidel a LLM, chování při chybě a nejistotě.
- Po funkčním průchodu: jednoduché UI, ukládání stavu a způsob předvedení.
- Nakonec: popis budoucí integrace MEDDI. API na akci není (zadání, s. 12).

Externí AI služba ani přenos dat nejsou zatím vybrané nebo schválené.
Do té doby pracujeme lokálně se syntetickými nebo schválenými daty.

## Příkazy

Platí v Linuxu i Windows PowerShellu z kořene repozitáře:

```text
uv sync --locked
uv run ruff check .
uv run pytest
```

`pytest` zatím nemá co spustit a skončí kódem 5 (žádné testy).
Příkaz aplikace a smysluplné testy doplníme s prvním implementačním krokem.
