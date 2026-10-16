# Technické řešení

Základ: Python 3.12 + uv, Linux / Windows PowerShell. Vývojové nástroje: pytest a Ruff.
Implementované jsou samostatné moduly `triage.py` a `llm_intake/` bez runtime
závislostí. CLI intake po potvrzení odpovědi volá triáž; pacientská karta
a celá aplikace zatím nejsou implementované. Rozhraní popisují následující oddíly.

## Minimální propojení intake → triáž

```text
uv run python -m llm_intake --question pocit
uv run python -m llm_intake --questionnaire bolest_analgeticka_terapie --question nrs
```

Po pacientově potvrzení CLI zavolá `triage.evaluate_intake(result)` a vypíše
barvu a upozornění na neúplné posouzení. `pocit` mapuje potvrzený index 0–4
na `overall_feeling` 1–5; `nrs` předává číselnou odpověď do `pain_nrs`.
Jiné otázky ani nepotvrzené návrhy nepřevádí na klinická fakta. Barvy možností
dotazníku se k určení výsledné triáže nepoužívají.

Příkaz stále řeší jednu otázku. Pocit 5 tak vrátí `orange`, bolest 4–6 `yellow`;
ostatní potřebné údaje zůstávají neznámé a `requires_review` je true.
Bez prokázané eskalace vypíše „neurčeno“, nikoli zelenou. Výchozí otázka
`unava` zatím nemá mapování. Kontext léčby ani měření se zde nedoplňují.

## Návrh: MASTER QUESTION a karta v čase

[master-question.md](master-question.md) propojuje otevřenou otázku se
`zprava_pacienta`, extrakcí faktů, výběrem témat, stávajícím intake a budoucími
kontrolami z karty. Omezená orchestrace LLM dialogu už existuje níže;
konzervativní vyhodnocení alternativ a napojení na kartu jsou zatím návrh.

Zásadní hranice: každá zpráva nejprve poskytne fakta pro nezávislou kontrolu
tvrdých pravidel; běžné doptávání ani potvrzení nesmějí blokovat již známé
urgentní předání. Nejistota má zůstat v datech; vyšší prozatímní úroveň vypočte
kód z podložených možných interpretací, nezapisuje se jako vymyšlená potvrzená
odpověď. Barvy možností nejsou úrovně triáže.

Současná triáž pokrývá jen část pravidel a intake při `unclear` nevrací
alternativy, takže celý tento bezpečnostní požadavek ještě neplní. První
samostatný LLM kontrakt je uveden níže; pokrytí pravidel a jejich adaptér
zůstávají úkolem budoucí integrace. Aktuálních 49 otázek nevyžaduje vektorovou databázi;
plánujeme explicitní katalog a výběr podle faktů, chybějících údajů a splatných
kontrol. Vedle limitu doptání jedné otázky potřebujeme i rozpočet celého kontaktu.

## Implementováno: LLM kontrakt MASTER QUESTION

[Popis rozhraní a příklad](../llm_intake/MASTER_CONTRACT.md):
`llm_intake.master_contract` definuje `MessageEvent`, `Fact`, `NumericRange`
a `build_packet(message, facts) -> dict`. Samostatný paket verze 1 obsahuje
původní zprávu a nepotvrzené fakty s citací, subjektem, nejistotou a časovým textem.
Neobsahuje triáž a nenahrazuje export intake v2. Čas dostupnosti a zdroj dodává
aplikace; relativní čas ani interval se nepřevádějí na domyšlené přesné měření.

`llm_intake.question_catalog.load_catalog()` čte všech 49 dvojic ID ze zdrojových
definic. `load_topic_catalog()` je spojí s `question_topics.json`: klíčová slova,
anglické aliasy a kontext pro každou otázku. Kontroluje přesnou shodu 49/49;
zdrojové otázky ani jejich možnosti nekopíruje. `resolve_topics(topic_ids)`
vrací balíčky z přesných ID; `lookup_questions(concepts)` zůstává kompatibilní
alternativou pro vlastní extraktory bez ID. Zachovává podmínky větvení,
ale nevyhodnocuje je. Jde o kandidátní vazby,
ne plánovač: i popření nebo potíž pečujícího má vazbu, kterou musí následný
výběr posoudit podle celého faktu a kontextu.

Pět syntetických příkladů v `llm_intake/master_examples.json` vymezuje požadovaný
převod a používá je nový extraktor níže. Omezený dialog už potvrzuje vybrané
odpovědi; samostatná fakta zůstávají návrhy. Karta, časování a triáž se zde neimplementují.

## Implementováno: extrakce MASTER QUESTION a kandidáti otázek

`llm_intake.master.MasterExtractor(client)(message)` vrací validovaný seznam
`Fact`. Vlastní `master_prompt.md` a `master_schema.json`, pět příkladů v kontextu
a celý katalog všech 49 otázek včetně klíčových slov a možností odpovědí.
Fakt obsahuje `topic_ids`, která striktní schéma omezuje enumem z katalogu;
kód validuje a mechanicky mapuje ID, bez top-k nebo embeddingů.
Pro model posílá text, typ, návod, poznámku a přesné možnosti; technická
metadata pořadí/podmínek zůstávají v aplikaci a exportu. Poznámka formuláře
je jednou v `questionnaire_context`. Katalog a příklady tvoří statický prefix
před proměnlivou zprávou. JSON pro API je kompaktní.
Model nedostává identifikátory
pacienta ani systémový čas; časová vyjádření zachovává doslovně. Další pojmy
uchová i bez odpovídající otázky. HTTP transport a autentizaci sdílí s intake
přes `Client.structured_payload()` a `Client.send()`.

`analyze_message(message, extract)` vrací pipeline paket s původní zprávou,
nepotvrzenými fakty a prázdným `question_answers`. Přidává `analysis_status`
(extracted/no_facts), `question_candidates` (balíček otázky + indexy důvodových
faktů), `unmapped_concepts` a `unknown_subject_fact_indices`. Popření a potíže
pečujícího nevyvolávají otázku na pacienta; fakta s neurčeným subjektem jsou
viditelná mimo automatický výběr. Kandidáti se neduplikují a respektují pořadí
definic, nikoli pořadí zmínek ve zprávě. Nejde o triáž ani hotový plán.

CLI pro zaznamenanou syntetickou odpověď, shodné pro Linux i PowerShell:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.master llm_intake/master_input.example.json
```

Na stdout je JSON, při chybě zpráva na stderr a kód 1. Nevalidní či nedokončený
výstup se nepřekládá na úspěšný prázdný výsledek. Samotné `no_facts` neznamená
dobrý stav pacienta. [Rozhraní a živý syntetický výstup](../llm_intake/MASTER_CONTRACT.md).
Kandidáty a již sdělené hodnoty propojuje `MasterDialogue` níže. Samotná funkce
`analyze_message` neposuzuje naléhavost, stáří nebo celkový rozpočet.

## Implementováno: omezený interaktivní MASTER dialog

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.dialogue --debug --output .scratch/master-output.json
```

`llm_intake.dialogue.MasterDialogue` spojuje extrakci zprávy, kandidáty,
`QuestionnaireFlow` a `Intake`. `start(MessageEvent)` zahájí kontakt;
`active` je aktuální cílená relace. Dále `submit(MessageEvent)`, `confirm()`,
`reject()`, `cancel()` a `snapshot()`. Předávaná odpověď musí mít nové ID,
správného pacienta, skutečnou otázku a čas ne starší než poslední zpráva.
Fakta všech slovních odpovědí se uchovávají a nová témata vstoupí do flow
po uzavření aktivní relace; už ukončené otázky se neopakují.

`Intake.seed(messages)` využije existující zprávy bez změny jejich původních
otázek. `submit_event(message)` připojí další odpověď se zdrojem. Úplný údaj
jde přímo k potvrzení, neúplný k doptání. `Client.extract_events` předává
modelu navíc autory zdrojů. Původní `submit(text)` a tříargumentový extraktor
zůstávají funkční. Export v2 přidá `source_events` jen při použití událostí;
pipeline `turns` pak doplní ID, čas dostupnosti a autora zdroje.

Kontakt má výchozí `max_questions=6` včetně MASTER, potvrzení a oprav;
`max_clarifications=2` dál omezuje jednotlivý parametr. Vyčerpání kontaktu je
`limited`, nedokončená větev či nepokrytý pojem `unresolved`, přerušení
`cancelled`, úspěšný sběr `complete` (nikoli klinické vyhodnocení). JSON
zahrnuje všechny zpracované `messages`, `facts` se správnými zdroji,
`question_answers` a `dialogue` se stavem, limitem a průběhem větví.
`dialogue.pending_topic_ids` zpřístupňuje připravené i blokované otázky,
které zbývají po vyčerpání rozpočtu; fakta a kandidáti se tím nezkracují.

CLI podporuje `/moznosti`, `/konec`, `--input`, `--debug`, `--output`,
`--max-questions`, `--max-clarifications` a simulovaný `--at`.
Bez vstupního souboru se ptá od MASTER; se souborem pokračuje z uložené
zprávy. Čas kontaktu se automaticky neposouvá. Chyba nezpůsobí potvrzení
ani prázdný úspěch; CLI skončí 1, může uložit dosud zpracovaný stav a nemá
automatické obnovení. Kódy 0/2 značí dokončený/neúplný nebo přerušený sběr.
Vyčerpaný rozpočet se kontroluje před další cílenou extrakcí; otevřená otázka
zůstává bez návrhu a původní rozpoznaná fakta se zachovají.
Katalog zahrnuje všechny zdrojové otázky; karta a bezpečnostní triáž nejsou
zapojené. To není úplné pokrytí klinických problémů ani záruka záchytu LLM.
Nezávislou syntetickou regresi spouští `llm_intake.evaluate_topics`;
[příkaz a interpretace](../llm_intake/README.md#ověření-rozpoznávání-témat).

## Implementováno: větvení otázek a předání LLM výstupu

[Review a diagram](llm-flow.md) popisuje tok i dosavadní mezery. `Question`
je společný balíček otázky, všech možností, návodu, poznámky, pořadí a podmínky;
využívá jej model, katalog i pipeline. Příklady drží pouze ID a při sestavení
promptu dostanou aktuální balíček ze zdrojových definic. Výlučnost „žádné účinky“
je malá explicitní politika; směr škály se předává bez popisu barev.

`QuestionnaireFlow(questionnaire_id, targets=None)` načítá pořadí a `podminka`
z definic, nevytváří druhý ruční graf. Bez `targets` prochází celý formulář;
s `targets` začne vybranými otázkami a zahrne jejich potomky. Rodiče mimo
rozsah nevyplňuje. `QuestionnaireFlow.for_targets(targets)` navíc automaticky
odvodí dotazník z prvního zadaného cíle. `next_question()` vrací další balíček nebo None;
`record(session)` přijímá pouze očekávaný ukončený intake. Větve aktivuje
potvrzená odpověď, ne návrh. `snapshot()` rozlišuje ready, blocked, unresolved
a complete; None z `next_question()` samo neznamená dokončený sběr.

`find_question(question_id, questionnaire_id=None)` umožňuje dohledat otázku
ze všech dotazníků bez nutnosti předem znát ID dotazníku; při kolizi ID vyžaduje
upřesnění. `create_targeted_session(question_id)` připraví hotovou `Intake` relaci
pro cílenou udržovací otázku. Kořenový balíček `llm_intake` exportuje ucelené
rozhraní pro zprávu, extrakci, katalog, relaci i sestavení pipeline paketu.

`build_pipeline_packet(message, facts, sessions)` vrací JSON typu `llm_intake`
verze 1: původní podnět `message`, nepotvrzené `facts` a `question_answers`
s balíčky, hodnotami, potvrzením, citací a historií skutečných otázek/odpovědí.
Nový výstup neobsahuje barvy. Odmítnuté a nevyřešené návrhy mají null;
samostatný starší export intake v2 zůstává zachovaný. Časy tahů ani původ faktů
se nevymýšlejí. Při předání událostí je již uchovává, u původního `submit(text)`
zůstávají neznámé.

Původní CLI stále řeší jedinou otázku, nabízí `/moznosti` bez API volání a má
`--max-clarifications`. MASTER má samostatné CLI nad zaznamenanou zprávou výše.
Interaktivní MASTER a rozpočet kontaktu jsou implementované v `dialogue` výše.
Nový pipeline paket zatím nemá adaptér triáže ani karty. CLI jedné otázky
používá pouze minimální propojení s triáží popsané výše.

## Implementováno: malá deterministická triáž

`triage.py` obsahuje čistou funkci `evaluate_triage(data)` a CLI:

```text
uv run python triage.py vstup.json
```

Vytvořte UTF-8 soubor `vstup.json`, například:

```json
{
  "temperature_c": 38.2,
  "chemotherapy_within_6_weeks": true,
  "spo2_pct": 97,
  "overall_feeling": 3,
  "pain_nrs": 2,
  "pain_persists_after_rescue_dose": false
}
```

Kontext chemoterapie dodá aplikace z léčebných údajů; zahrnuje probíhající
chemoterapii nebo období do 6 týdnů po ní. LLM pouze převádí sdělená fakta,
neurčuje tento kontext klinickým odhadem. Teplota je kladné konečné číslo
ve °C, SpO2 číslo 0–100 %, pocit celé číslo 1–5 (5 = velmi špatně),
bolest celé číslo NRS 0–10. Kontext chemoterapie a přetrvávání bolesti po
SOS dávce jsou boolean. Není-li známo, zda SOS dávka byla užita a zabrala,
`pain_persists_after_rescue_dose` musí být `null`, nikoli `false`.

Všechna pole lze vynechat nebo nastavit na `null`; neznámá hodnota se nenahradí
nulou. Prototyp předpokládá správně připravený JSON s typy a rozsahy uvedenými
výše. Nemá vlastní validátor ani obsluhu výjimek; chyby souboru, JSON nebo typů
nechává zobrazit přímo Python. Výsledek vypisuje jako JSON na stdout.

Implementované podmínky podle pravidel balíčku, oddíly 3–4:

- Červená: teplota ≥ 38 °C v kontextu chemoterapie nebo SpO2 < 90 %.
- Oranžová: SpO2 < 92 %, pocit 5 nebo bolest NRS ≥ 7 přetrvávající po SOS dávce.
- Žlutá: bolest NRS 4–6.
- Platí nejvyšší aktivovaná úroveň; zelená znamená jen absenci nálezu v této sadě.

Každé kritérium má vlastní funkci: `fever_score`, `oxygen_score`,
`overall_feeling_score`, `pain_score`. Funkce vrací 1–4 (green až red),
případně `None`, když nelze kritérium uzavřít. Úrovně jsou `Severity(IntEnum)`:
`GREEN = 1`, `YELLOW = 2`, `ORANGE = 3`, `RED = 4`. `evaluate_triage` spočítá
maximum známých skóre. Skóre se nesčítají.
Každá funkce má anglický docstring s odkazem na soubor a konkrétní oddíl pravidel.
V JSON se enum automaticky zapíše jako číslo; barva zůstává anglický řetězec.

Výstup obsahuje `color`, `scores` (skóre jednotlivých kritérií) a
`requires_review`. Nahrazuje předchozí výstup s textovými důvody a seznamem
chybějících polí. `null` ve skóre označuje kritérium k posouzení. Pokud jsou
známá skóre jen zelená a jiné kritérium není vyřešené, výsledná barva je
`null`. Prokázaná vyšší barva zůstává minimem i při neúplných údajích.
Silná bolest bez potvrzeného přetrvávání po SOS dávce zůstává k posouzení.

Jde o omezenou sadu, nikoli úplnou triáž ani klinicky ověřený systém.
Zatím nezpracovává zimnici, pokles saturace proti obvyklé hodnotě, další
příznaky, trendy ani kontakty. Načítání historie ani napojení na `llm_intake/`
nejsou v triáži zapojené.
Zdroj: [pravidla triáže](../rakathon_meddi_onco_data/docs/pravidla_triaze.md),
oddíly 3–4. Rozšiřování pravidel bude pokračovat po review tohoto souboru.

## Samostatný modul LLM intake

Cílený klient z banky třinácti příkladů posílá nejvýše tři: nejprve shodnou
otázku, pak stejný typ. Výběr nezávisí na textu odpovědi a zachovává stabilní
prefix. `Client(on_usage=callback)` umožňuje odečíst skutečné tokeny, cache,
reasoning a dobu volání bez logování obsahu; nastaví se například přes
`dataclasses.replace(Client.from_env(), on_usage=callback)`. Chybějící
metriky jsou null. Evaluátor je připojuje do `api_usage` reportu.
Rozhraní klinického paketu se tím nemění.

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.evaluate_topics --cases tests/fixtures/master_precision_cases.json --output .scratch/master-precision.json
```

Vedle minimálního pokrytí evaluátor umí `allowed_topics` a `fact_checks`.
Nepovolená témata, nesprávný subjekt, negace nebo hodnota jsou neúspěch;
`topic_precision` má jmenovatel jen na plně označené sadě. Měření tokenů
a jeho limity popisuje [README modulu](../llm_intake/README.md#spotřeba-tokenů).

[llm_intake/README.md](../llm_intake/README.md) popisuje CLI, Python API,
konfiguraci a export `schema_version=2`. Modul používá jednu explicitně vybranou
otázku z definic: slovní odpověď → přiřazení k interní možnosti → pacientovo
potvrzení slovního znění nebo oprava. Při nejasnosti LLM položí krátkou navazující
otázku podle chybějícího rozlišení možností; neopakuje celý dotaz. Kontext zahrnuje
otázky i odpovědi. Výchozí limit dvě doptání řídí kód; bez vyřešení zůstane stav
`unresolved`, bez vymyšleného výběru. Export obsahuje historii a počty tahů.
Pacient předem nevidí možnosti ani barvy.
Stav drží Python; potvrzení nevytváří LLM. Kolegové se napojují přes `Intake`
a potvrzený JSON, bez závislosti na CLI. Nejde zatím o obecné schéma karty pacienta.

Výchozí model je `gpt-6.1-sol`, jeho deployment `gpt-6-1-sol-dz-eu` se nastavuje
přes `MEDDI_LLM_MODEL`. Dodaná brána vyžaduje `MEDDI_LLM_KEY_HEADER=api-key`.
Adaptér používá dodanou OpenAI kompatibilní bránu a Chat Completions se striktním
JSON schématem. Implementace používá jen standardní knihovnu, `pyproject.toml`
a `uv.lock` nebylo potřeba měnit. Klíč v `MEDDI_LLM_API_KEY` se načítá z prostředí;
lokální `llm_intake/.env` lze načíst přes uv a Git ho ignoruje.

```text
uv run python -m llm_intake --list
uv run --env-file llm_intake/.env python -m llm_intake --question unava
uv run python -m pytest tests/test_llm_intake.py -q
```

Rozsah: jedna otázka a potvrzovací cyklus; průchod podmíněnými otázkami,
pacientská karta, časování a triáž zůstávají oddělené. Testy nahrazují LLM i HTTP
transport. Živé volání brány se syntetickou odpovědí je ověřené; systematické
měření kvality modelu zůstává další krok. Export přidává `signaly_odpovedi`:
původní barvy možností načítá deterministicky kód, nejsou výslednou triáží.
V CLI se interní JSON vypisuje pouze s `--debug`, Python rozhraní jej vrací přímo.
Nový kontrakt extraktoru: `extract(question, source_messages, source_questions)`.
Pro současný počet možností nepřidáváme RAG ani embeddingy. Správnost přiřazení
a nutnost doptání budeme měřit na označených scénářích; skóre podobnosti ani
nekalibrované procento LLM zatím nepoužíváme jako rozhodovací práh.

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

Následující text popisuje cílové propojení; aktuální rozsah samostatných modulů
je uveden výše.

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
(README balíčku, oddíl 6). Výchozího kandidáta a adaptér popisuje modul výše. Klinická pravidla
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

API adaptér je ověřený na dodané bráně se syntetickou odpovědí. LLM dostává
pouze jednu otázku, interní texty možností a odpovědi k ní, nikoli barvy.

## Příkazy

Platí v Linuxu i Windows PowerShellu z kořene repozitáře:

```text
uv sync --locked
uv run ruff check .
uv run pytest
```

Testy pytest existují pro `llm_intake/`. Ověření prvního `triage.py`
proběhlo samostatnými kontrolami funkce a CLI; rozsah a výsledek jsou v tasks.md.
CLI intake navíc vypisuje omezenou triáž podle propojení popsaného výše.

## Porovnání barev dotazníků s referencemi

Z `origin/main` pochází také `meddi/form.py`, `meddi/loader.py`,
`meddi/common_types.py`, `meddi/triage.py` a porovnávací CLI `main.py`.

```text
uv run python main.py
uv run python -m meddi.triage vstup.json
```

`main.py` porovnává maximum barev dotazníků s referencemi párovanými podle
`checkin_id`; nevytváří kontextovou triáž ani důkaz její klinické správnosti.
Reference se načítají pouze pro porovnání. Propojení intake nadále používá
kořenový `triage.py`; implementace v `meddi/triage.py` je zatím samostatná.
