# Finální technická kontrola scénářů · 17. 10. 2026

Rozsah: znovu ověřit šest povinných situací, jejich mezní/negativní
protějšky a několik skutečných extrakcí. Podmínkou dokončení této kontroly
je doložený výsledek a přiznané mezery; nejde o klinické převzetí ani uzavření
auditů K6/K7/K9. Aplikační kód, konfigurace modelu a původní data se neměnily.

Zdrojem seznamu je `documents/MEDDI – MEDDI Onco.pdf`, s. 9; způsob
chronologického ověřování a kritéria hodnocení jsou na s. 10–11.
Konkrétní minima vycházejí z
[`pravidla_triaze.md`](../rakathon_meddi_onco_data/docs/pravidla_triaze.md),
§3–6. Následující výsledky jsou technická pozorování implementace nad
syntetickými vstupy; klinickou interpretaci musí převzít kvalifikovaný člověk.

| Situace | Znovu ověřený aplikační průchod bez API | Zdroj pravidla a omezení |
| --- | --- | --- |
| Horečka v období nadiru | 38,2 °C desátý den od uvedeného D1 → červená, uložená teplota a zdroj léčby; 37,9/38,0 °C jako hranice | §3 / Horečka, §5 / Den 7–14. D1 zde není úplná evidence skutečného podání ani laboratorní důkaz neutropenie (O7) |
| Imunitní kolitida zhoršující se během dvou dnů | Na nivolumabu 2 → 5 → 2 stolice nad normál, bolest a její odeznění → minima žlutá → oranžová → žlutá | §3 / Průjem, §4, §6.1 a §6.3. Jde o záchyt rizika, nikoli sdělení diagnózy |
| Plíživé srdeční obtíže | 70 → 72,5 kg za tři dny při trastuzumabu → žluté minimum; nová ortopnoe → oranžové; hranice +2 kg nezapne pravidlo pro >2 kg | §4 / Hmotnost, §3 / Dýchání, §6.1 |
| Interakce a krvácení | Kapecitabin + časově platný warfarin + krev ve stolici → červená; nové modřiny a budoucí lék mají vlastní kontroly | §3 / Krvácení, §5 / Antikoagulace. Není to obecný interakční engine |
| Paliativní pacientka, píše dcera | Autor pečující, její vyčerpání oddělené od pacientčiných příznaků → žluté minimum a 24h paliativní tým/hospic se záložní 155; paliativní kontext nepotlačí červenou | §4 / Pečující, §5 / Paliativní péče, §6.7 |
| Rozpor zprávy a dotazníku | 38,5 °C proti mírnější potvrzené volbě → červené minimum a viditelný `conflicting_temperature`; souhlasící odpověď nevytvoří falešný rozpor | §3 / Horečka, §6.2 a §6.4 |

Průchody v `tests/test_mvp_scenarios.py` zahrnují formulář → potvrzení →
uložený výsledek → report/kartičku týmu, limit šesti otázek a oddělení
budoucích informací. Extrakce je v automatických testech nahrazená.

## Provedené kontroly

Z kořene repozitáře, Python 3.12 přes uv; příkazy lze použít i v PowerShellu:

```text
uv run --locked python -m pytest -q tests/test_mvp_scenarios.py tests/test_demo_export.py tests/test_patient_portal.py
uv run --locked python -m pytest -q
uv run --locked python -X utf8 tests/acceptance_meddi/run.py validate
uv run --locked python -X utf8 tests/acceptance_meddi/run.py list --tag required-six
uv run --locked ruff check .
git diff --check
```

Výsledky: **64 cílených testů prošlo**, celá sada **985 prošlo**,
Ruff bez nálezu. Validace přijímací sady potvrdila 502 scénářů / 140
požadavků; spustila **0 aplikačních testů**. Její validaci nelze vydávat za
splnění 502 scénářů aplikací. V omezeném prostředí byl u části příkazů
použit `uv run --locked --cache-dir /tmp/meddi-uv-cache`, protože výchozí
cache nebyla zapisovatelná. Windows se přímo netestoval.

## Omezená živá kontrola

Použita současná konfigurace `deepseek-v4-pro-global`, bez změny parametrů.
Celkem **3 sekvenční API volání**, bez opakování a bez SMTP; jen syntetické
zprávy. Model dostal text, otázku, autora a společný katalog, nikoli názvy
scénářů nebo očekávání. Léčebný kontext dostalo následně místní triážní jádro.

| Zpráva | Skutečný výsledek | Čas samotného API |
| --- | --- | --- |
| „Dnes mám teplotu 38,2 °C.“ | API extrakce doběhla. Pomocný skript následně selhal na chybějícím `messages`; návazná triáž tohoto pokusu není doložená | 2,288 s |
| „Za posledních 24 hodin mám 5 průjmových stolic nad svůj normál. Bolí mě břicho.“ | Živá extrakce → místní adaptér → oranžové minimum i výsledná barva na nivolumabu; předchozí den se 2 stolicemi byl připraven offline | 4,003 s |
| „Maminka je bez nových potíží. Já už jsem jako pečující vyčerpaná.“ | Živá extrakce zachovala `caregiver_exhaustion` u pečující; žluté minimum i výsledná barva, `palliative_team_24h` | 2,260 s |

U průjmu model vydal jak `diarrhea.increase_over_baseline`, tak
`diarrhea.episodes`. První údaj se správně použil jako 5 stolic nad normál;
druhý zůstal jako `unsupported_or_nonexact_finding` k review. Závažnost se
nesnížila. Oba dokončené živé průchody byly záměrně hodnocené jako
rozpracovaný kontakt (`needs_answer`), proto `requires_review=true` není
prohlášení o dokončeném rozhovoru. Žádné cílené odpovědi se živě nedotazovaly.

Lokální diagnostika je v ignorovaných `.scratch/final-live-check.json`,
`.scratch/final-live-colitis-packet.json`, `.scratch/final-live-caregiver-packet.json`
a pomocném `.scratch/final_live_check.py`. Souhrnný skript vrací neúspěch
kvůli prvnímu nedokončenému pokusu; dva následné záznamy mají `passed=true`
pro kontrolované minimum a u pečující také autorství/kontakt. Nejde o
tři úspěšné živé scénáře ani o celý živý průchod prohlížečem.

Zbývá kvalifikované klinické převzetí, původní audity a úplné ověření
živého dialogu. Přesně popsané duplicity/mezery v extrakci nepřekrýváme
zeleným výsledkem; další API volání se v této kontrole neprováděla.

## Opravené ověření horečky na následný pokyn uživatele

První chyba byla v pomocném testu: `analyze_message` vrací zprávu, fakta
a kandidáty otázek, zatímco `web.export.meddi_record` očekává také
`packet["messages"]`. Test tento mezikrok vynechal. Běžný web předává
snapshot `MasterDialogue`, který seznam zdrojových zpráv vytváří.
Nešlo o doložené selhání detekce horečky v aplikaci.

Náhradní pomocný test `.scratch/final_fever_recheck.py` nyní používá
skutečný `MasterDialogue.start` s triážním checkpointem jako web.
Protože první extrakce horečky nebyla uložená, provedl se na následný
pokyn uživatele **jeden nový API požadavek**, 1,710 s; celkem tedy čtyři
volání za původní kontrolu a tuto opravu. Bez cílených API volání.
Nový skript uloží extrakci před návaznými kroky a výchozí spuštění
ji pouze přehraje; `--live` při existující cache další volání odmítne.

Ověřený výsledek pro „Dnes mám teplotu 38,2 °C.“ s původním syntetickým
léčebným kontextem: **červená**, `neodkladna_pomoc`, „155 / urgentní
příjem ihned.“ Dialog přešel do `paused` ještě před cíleným dotazováním.
Export zachoval přesných 38,2 °C a původní zprávu. To odpovídá pravidlům
triáže §3 / Horečka a §2; klinické převzetí zůstává otevřené.

Živý výsledek je v `.scratch/final-live-fever-repaired.json`, extrakce
v `.scratch/final-live-fever-extraction.json`; původní neúspěšný pokus
zůstává zachovaný. Následné přehrání stejné extrakce bez API prošlo rovněž
(`.scratch/final-live-fever-replay.json`). Cílené aplikační regrese:

```text
uv run --locked python -m pytest -q tests/test_mvp_scenarios.py -k "fever or temperature or milder"
```

**5 prošlo**, 41 ostatních testů tohoto souboru nebylo vybráno. Ověřují
horečku, hranice, mírnější odpověď a souhlasící teplotu. Aplikační kód
ani jeho rozhraní tato oprava nemění.
