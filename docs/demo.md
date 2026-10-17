# Demo MEDDI ONCO

Praktický podklad pro M5: živý průchod, samostatná offline záloha, rozsah
ověření a návrh integrace. Optimalizace LLM patří až na konec podle
[tasks.md](tasks.md#priority-do-dokončení-mvp). Všechny vstupy zde jsou
syntetické. Mobil/desktop a prohlížečový cyklus kontroly jsou ověřené;
klinické převzetí mentorem a závěrečný živý nácvik stále zbývají.

## Termín a rozsah prezentace

Uživatel 17. 10. 2026 kolem 10:00 Europe/Prague upřesnil odevzdání
„za tři hodiny přesně“. Pracovní nejzazší bod této relace je tedy
**17. 10. 2026 ve 13:00 Europe/Prague (11:00 UTC)**. Délka prezentace zatím
není omezená; cílem je předvést existující MVP včetně detailů.
Formát/místo odevzdání a požadavek na veřejnou URL dosud potvrzené nejsou.
Do odevzdání upřednostnit chyby bránící předvedení a ověření hotového toku;
finální optimalizace LLM zůstává posledním implementačním krokem.

## Příprava

Python 3.12 + uv, z kořene repozitáře; stejné příkazy na Linuxu i v PowerShellu:

```text
uv sync --locked
uv run --locked python -m scripts.build_demo
uv run --locked pytest -q tests/test_mvp_scenarios.py tests/test_patient_portal.py tests/test_doctor_followup.py tests/test_demo_export.py
```

Export vytvoří `dist/demo/index.html` a `dist/demo/results.json`. HTML má
vložené styly, nepoužívá JavaScript, vzdálené zdroje, server, LLM ani SMTP.
Po vytvoření jej lze otevřít přímo ze souboru bez připojení. Oba soubory
přenést na prezentační počítač a předem ověřit otevření. Export spouštět
před prezentací v připraveném Python prostředí, nikoli až při výpadku sítě.

Pro živý web použít současnou konfiguraci v `llm_intake/.env` podle
[návodu](architecture.md#spuštění-a-kontroly). Potřebuje platné LLM nastavení
a obě hodnoty Basic Auth. Model nyní nepřelaďovat. Pro opakovatelný nácvik
nastavit `MEDDI_DATA_DIR` na nový lokální adresář, např.
`data/demo-rehearsal-01`; pro další čistý nácvik zvolit nový název.
Předchozí pracovní kopie ani původní zdroje se nemažou.

```text
uv run --locked python -m web.app
```

Otevřít http://127.0.0.1:5000. Přihlášení Basic Auth chrání celé demo;
následující pacientský kód pouze simuluje vlastní účet. Kódy a fiktivní
profily jsou v odděleném ovládání „Ukázkové účty“.

## Živý průchod

1. **Pacientský portál.** Zvolit Pacient, zadat demo kód `ONC-001`.
   Ukázat MASTER, poslední uložený stav s časem, „Co sleduji“ a rozbalitelné
   vlastní údaje. Historické hodnocení není dnešní nové posouzení.
2. **Běžný stav.** Napsat `dobrý`. Očekávaný tok nabídne jediné upřesnění
   celkového stavu; zodpovědět skutečnou škálu (např. `1`) a potvrdit
   souhrn. Samotné obecné „dobrý“ nesmí znamenat odhad nulových příznaků.
   Při běžné přesné odpovědi bez dalšího rizika má následovat sledování.
3. **Aktualizace sledovaného údaje.** U existující teploty v „Co sleduji“
   kliknout „Aktualizovat měření“, napsat `Právě jsem naměřil 36,8 °C.`
   a dokončit případné relevantní upřesnění i potvrzení. Ukázat novou
   hodnotu, čas a „Aktualizováno“. Kliknutí bez uložené odpovědi nestačí.
   Termín a volitelný interval připraví tým v detailu profilu pod
   „Naplánovat / upravit kontrolu“. Pro ukázku neodpovědi lze výslovně
   zadat již uplynulý termín. Obě rozhraní ukážou „po termínu“; po uložené
   odpovědi vznikne další termín pouze podle zadaného intervalu.
   Jde o ukázkový plán, nikoli odhad klinického intervalu aplikací.
4. **Okamžitá pomoc.** Zahájit novou pravidelnou kontrolu a napsat
   `Jsem náhle zmatený a nevím, kde jsem.` Ukázat naléhavou instrukci
   ještě před cíleným doptáváním a konečným potvrzením. Ve fiktivním
   scénáři lze následně výslovně pokračovat, doplnit údaje a uložit výsledek.
5. **Lékař.** Přes demo patičku zvolit rozhraní Lékař. V `/team` otevřít
   aktuální kartičku stejného profilu: důvod, krok, kontakt, termín,
   neúplnost zvlášť. Ukázat hledání a filtry „Naléhavé / Po termínu /
   K doplnění“. V detailu nejdřív stručný souhrn, léčbu, zdrojované trendy
   a časovou osu, potom plán kontroly nebo záznam kontaktu týmu.
   Úplná historie/graf jsou v rozbalení. Předání je simulované;
   během průchodu neposílat e-mail.
6. **Zastupování a další situace.** Na novém kontaktu ukázat nenápadné
   přepnutí pečujícího a změnu oslovení. Ostatní klinické situace lze
   stručně projít v připravené offline ukázce se zřetelným označením režimu.

Živý LLM může vyžádat jiné relevantní upřesnění. Neklikat mechanicky na
mírnější odpovědi: potvrdit pouze skutečný význam syntetického vstupu.
Celý průchod v prohlížeči před porotou je nutné nacvičit; export jej
neprovádí. Technický nácvik přes skutečné formulářové handlery se skutečným
nakonfigurovaným LLM je popsán níže. Data pořadatelů jsou z roku 2026 a živý web používá
skutečný čas serveru. Konkrétní vazby na podání léčby ověřit pro datum
nácviku; offline ukázka má své časy výslovně zmrazené.

Lokální Chrome nácvik nové návaznosti prošel se syntetickým profilem:
plán týmu → neodpověď v přehledu i portálu → nové měření → potvrzení →
další explicitní termín → odstranění z filtru neodpovědí. Ověřeno i načtení
grafu až po rozbalení podkladů, bez JS chyb. LLM byl v tomto průchodu
nahrazený a SMTP blokované; nejde o nové živé ověření extrakce.
Vizuální kontrola 1440/390 px neukázala vodorovné přetečení.

## Přechod na offline zálohu

Při nedostupném LLM nebo nepoužitelném čekání oznámit přechod na
**předpřipravenou offline ukázku** a otevřít `dist/demo/index.html`.
Živá aplikace nepřepíná automaticky na uložené odpovědi. Její již přijatá
zpráva a případná naléhavá instrukce zůstávají v původním toku.

Záloha vychází z [demo/cases.json](../demo/cases.json). Zprávy, ručně
připravené extrahované fakty a případná potvrzená odpověď vstupují přes
stávající intake kontrakt do `web.triage.assess_contact`, sdíleného jádra
a exportu. Mezi kroky se přidává pouze už dostupná historie. Názvy situací
ani očekávané výsledky nejsou vstupem rozhodování. LLM ani celý živý
rozhovor se tím neověřují; neúplnost a rozpory zůstávají viditelné.

| Situace | Předvedený podklad | Minimum současné implementace v připravené ukázce |
| --- | --- | --- |
| Horečka po léčbě | 38,2 °C a doložený léčebný kontext | Červená |
| Průjem na imunoterapii | 2 → 5 stolic nad normál s bolestí → 2 bez bolesti | Žlutá → oranžová → žlutá |
| Plíživé srdeční obtíže | 70 → 72,5 kg za 3 dny, potom nová ortopnoe | Žlutá → oranžová |
| Interakce a krvácení | Kapecitabin, časově platný warfarin, krev ve stolici | Červená |
| Paliativní pacientka a dcera | Vyčerpání pečujícího odděleně od pacientových obtíží | Žlutá, vlastní paliativní tým s náhradní pomocí |
| Zpráva proti dotazníku | 38,5 °C proti mírnější potvrzené volbě | Červená a viditelný rozpor |

Jde o technické příklady, které ještě musí nezávisle převzít klinický mentor.
Zdroje šesti situací: [zadání MEDDI](<../documents/MEDDI – MEDDI Onco.pdf>),
s. 9; hodnocení s. 10–11. Interpretace a kontakty:
[pravidla triáže](../rakathon_meddi_onco_data/docs/pravidla_triaze.md), §2–6.
Použití D1 jako podkladu léčby není úplný registr skutečných podání (O7).

## Rozsah technického ověření

Aktuální [finální kontrola šesti situací](final-check.md) z 17. 10. 2026
dokládá opakování automatických průchodů a omezenou živou kontrolu.
Po opravě pomocného testu horečky jsou doložené tři průchody extrakce →
triáž (horečka, průjem, dcera), čtyři API volání celkem včetně původního
nedokončeného pokusu. Horečka prošla přes skutečný dialog a naléhavý
checkpoint před cíleným dotazováním. Nenahrazuje klinické převzetí.

Technický nácvik M5 přes Flask formuláře a skutečný LLM ověřil:
`dobrý → skutečná odpověď na škálu → potvrzení → zelená`; po opravách také
`Právě jsem naměřil 36,8 °C. → uložení → aktualizovaná kontrola → zelená`
bez neodpověditelné horečkové otázky a
`Jsem náhle zmatený a nevím, kde jsem. → naléhavá instrukce před potvrzením
→ červený uložený výsledek → stejná kartička týmu`. Ukázkový termín kontroly
byl ručně označený v izolované kopii dat; ověřeno bylo i přepnutí pečujícího
a odhlášení. Původní soubory se neměnily a SMTP se nevolalo.

První běžný průchod prošel samostatně; návazná část po opravách použila
jeho skutečný intake jako přípravu historie a nové živé extrakce pro měření
i zmatenost. Nejde o jeden nepřerušený prohlížečový nácvik. Diagnostika je
lokálně v ignorovaných `.scratch/m5-live-rehearsal*.json` a
`.scratch/m5-measurement-extraction.json`; první neúspěšné pokusy zůstávají
oddělené od ověřeného pokračování `m5-live-rehearsal-verified.json`.
Model a parametry se v této práci neměnily; žádné porovnání rychlosti se nedělalo.

- `tests/test_mvp_scenarios.py` ověřuje pacient → potvrzení → uložené
  hodnocení → report/kartička, šest situací i běžné, mezní a negativní
  případy. Extrakci nahrazuje syntetický model; nejde o živou LLM evaluaci.
- `tests/test_patient_portal.py` ověřuje demo vstup, změnu profilu,
  konkrétní otázku/měření, potvrzení, chybu a časovou izolaci.
- `tests/test_demo_export.py` ověřuje minima připravených případů,
  oddělení názvů/budoucích kroků a export bez externích volání a zápisu
  do pacientského úložiště.
- Export zároveň spustí existující `main.compare_patients` se
  `with_messages=False`. Výsledky jsou v `results.json` a rozbalitelné
  části HTML. Základní replay původních 14 pacientů / 171 check-inů nyní
  vykazuje **87 shod, 8 nižších, 76 vyšších výsledků, 0 neurčených**;
  `requires_review` je u 171 záznamů. To není hodnocení kvality celého
  produktu: jde pouze o strukturovanou cestu bez extrakce zpráv.
  Rozbor nižších/vyšších výsledků a příčin neúplnosti zůstává původnímu
  vlastníkovi auditu K7/K9; vyšší výsledek není automaticky zbytečná eskalace.

Opakování existujícího offline replay:

```text
uv run --locked python main.py --without-messages
uv run --locked python main.py --without-messages --comparison lower --details
uv run --locked python main.py --without-messages --comparison higher --details
```

Reference jsou načtené pouze hodnoticí větví. Offline export neprovádí
novou síťovou extrakci a neprohlašuje původní audit za uzavřený.
Poslední omezené živé kontroly M3 nenahrazují nácvik celé prezentace.

## Návrh napojení na MEDDI a EU provoz

Toto je **návrh kontraktu**, nikoli implementované MEDDI API. Zadání
výslovně požaduje návrh integrace bez dostupného API (S1 s. 12;
[pacientská cesta](../rakathon_meddi_onco_data/docs/pacientska_cesta_meddi_onco.md),
oddíl Technická integrace).

| Navržená operace adaptéru | Vstup / výstup | Současný základ |
| --- | --- | --- |
| Načíst kontext k času | Pacient a `as_of` → léčba, měření a historie s původem a dostupností | `patient_inputs`, časové filtrování; produkční čtení MEDDI chybí |
| Přijmout zprávu / měření | Stabilní ID události, pacient, autor, skutečná otázka, originál, jednotka a časy | SQLite přijetí před LLM, validace, oddělení autora/subjektu |
| Uložit hodnocení | ID kontaktu, čas/verze pravidel, vstupy a důvody, minimum/úroveň/úplnost, doporučení a `routing` | Uložený check-in a `triage_assessment`; zápis do MEDDI chybí |
| Vytvořit požadavek týmu | Stejné hodnocení, priorita, příjemce a vypočtená lhůta → ID a stav přijetí MEDDI | `/team` a kartička pouze simulují předání; potvrzení příjmu/doručení/převzetí chybí |
| Vrátit postup a kontroly pacientovi | Doporučení, zdroje a konkrétní kontrola → odpověď/měření do stejného toku | Portál, malá evidence kontrol; produkční plán/push není zaveden |

Pravidla zůstávají v jediném deterministickém jádře. LLM dostane pouze
nezbytné povolené údaje k extrakci; neurčuje prioritu, kontakt ani lhůtu.
Pacientský výstup i lékařská zpráva používají stejné uložené hodnocení.

Cílově se adaptér, úložiště a schválené zpracování LLM provozují v EU
prostředí dohodnutém s MEDDI/pracovištěm; zadání uvádí AWS v Evropě
(S1 s. 7 a pacientská cesta, Provoz). Dosavadní prototypová gateway ani
připravený Azure ZIP nejsou dokladem vhodnosti pro ostrá data nebo EU
provoz. Přístupy, obnovu, odpovědnosti a spolehlivé předání je nutné
dohodnout při skutečné integraci; pro toto syntetické demo se nezavádějí.

## Co ještě uzavřít

- Vizuální převzetí portálu i offline HTML na prezentačním desktopu/mobilu
  a celý prohlížečový nácvik. Živé formulářové handlery jsou ověřené výše;
  HTML/testy nenahrazují kontrolu skutečného zobrazení a ovládání.
- Klinické převzetí M3 a původní audit výsledků; předání zůstává simulované.
- Potvrdit formát/místo odevzdání a případný požadavek na vzdálenou URL.
  Termín a neomezenou délku prezentace upřesnil uživatel výše; lokální PDF
  zadání (s. 1–12) a úvodní prezentace (slidy 1–5) je neobsahují.
- Až nakonec provést MUST HAVE měření/optimalizaci LLM a opakovaný nácvik
  se zvolenou konfigurací. Tento export model ani jeho parametry nemění.
