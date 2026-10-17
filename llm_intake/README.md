# LLM intake: jedna otázka a potvrzení

Web navíc používá obnovený `MasterDialogue`: úvodní zpráva → témata a podmíněné
otázky → společná kontrola návrhů (`bulk_confirmation=True`). `review_sessions`
vrací návrhy, `revise(index)` otevře slovní opravu a zneplatní podřízené odpovědi,
`confirm_all()` potvrdí pouze vyřešené návrhy. Výchozí režim nadále potvrzuje
jednotlivé otázky. Ukládání souhrnu pro vybraný profil řeší web; podrobnosti
jsou v [architektuře](../docs/architecture.md#web).

Samostatný modul pro první experimenty. Pacient vidí otázku a odpovídá vlastními
slovy. LLM sémanticky přiřadí odpověď k možnosti z interních definic a pacient
potvrdí její slovní znění. Nabídka možností se pacientovi předem nezobrazuje.
Při odmítnutí přijme opravu a celý cyklus zopakuje. Nemění pacientská data,
nečte reference a nespravuje kartu ani časování kontaktů. Samotný intake
neprovádí triáž; CLI po potvrzení zavolá `triage.evaluate_intake()` pro pocit
a NRS a vypíše omezený výsledek včetně neúplnosti posouzení.

Pro otevřený popis stavu je vedle tohoto průchodu připravený samostatný
[kontrakt MASTER QUESTION a katalog vazeb](MASTER_CONTRACT.md).
Obsahuje už LLM extraktor otevřené zprávy, kandidátní otázky podle faktů
a omezený interaktivní dialog s potvrzováním vybraných odpovědí.
Pro ručně vybraná témata už existuje `QuestionnaireFlow` a společný výstup
`build_pipeline_packet()`: [rozhraní, diagram a výsledek review](../docs/llm-flow.md).

První běh MASTER nad připravenou syntetickou zprávou (výstup je JSON):

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.master llm_intake/master_input.example.json
```

[Návod a formát výstupu](MASTER_CONTRACT.md),
[ukázka živého syntetického výsledku](master_output.example.json).

## Interaktivní MASTER QUESTION

Z kořene repa na Linuxu i Windows PowerShellu, klíč ve stávajícím `llm_intake/.env`:

```text
uv sync --locked
uv run --locked --env-file llm_intake/.env python -m llm_intake.dialogue --debug --output .scratch/master-output.json
```

Program položí „Jak se dnes cítíte?“. Pro syntetický test napište například
„Za posledních 24 hodin jsem dvakrát zvracel. Jsem hodně unavený, teplotu nemám.“
Úplné údaje nabídne rovnou k potvrzení `ano/ne`; chybějící rozlišení doplní
konkrétním dotazem. Po `ne` přijme opravu a znovu nabídne potvrzení.
`/moznosti` ukáže texty odpovědí, `/konec` ukončí kontakt.

`--debug` vypíše konečný JSON včetně návrhů a nevyřešených údajů;
`--output` jej zároveň uloží do zadané cesty (rodičovský adresář vytvoří).
`.scratch/` Git ignoruje. Bez obou voleb se interní JSON nezobrazuje ani neukládá.
Výchozí `--max-questions 6` počítá MASTER, doptání, potvrzení i žádosti o opravu;
`--max-clarifications 2` navíc omezuje doptání jednoho parametru.
Po dosažení limitu zůstane kontakt `limited`, bez vynuceného potvrzení.

Pro start ze zaznamenané zprávy:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.dialogue --input llm_intake/master_input.example.json --debug
```

Katalog pokrývá všech 49 otázek čtyř dotazníků. LLM dostává celý katalog
klíčových slov, kontextů a balíčků otázka + možnosti; vrací přesná `topic_ids`.
Kód je mechanicky propojí s cíleným flow. Nastavení je v
[question_topics.json](question_topics.json); chybějící či nadbytečná otázka
oproti zdroji způsobí chybu, nemůže tiše vypadnout z promptu.

Jde o LLM prototyp bez vyhodnocení naléhavosti a bez karty. Potíže mimo katalog
zůstávají v JSON včetně `unmapped_concepts`. Po limitu se další rozpoznané
otázky uchovají v `dialogue.pending_topic_ids`; úplnost katalogu tedy neznamená
povinnost položit 49 otázek. Čas je simulovaný,
výchozí `--at 2026-10-16T10:00:00+02:00`; během kontaktu se automaticky neposouvá.
Podrobný kontrakt a Python rozhraní: [MASTER_CONTRACT.md](MASTER_CONTRACT.md).

## Ověření rozpoznávání témat

Samostatná sada 53 syntetických případů pokrývá každou otázku, více témat,
popření, potíže pečujícího a problém mimo katalog. Tyto odpovědi nejsou
promptovými příklady. Živé ověření přes nastavené API:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.evaluate_topics --output .scratch/master-topics-evaluation.json
```

Provádí placená API volání; `--case ID` vybere konkrétní případ. Výchozí
`--workers 1` omezuje souběh. Report měří záchyt očekávaných témat pouze
u validních odpovědí, zvlášť vypíše nevyhodnocené případy, témata navíc a chyby.
Nejde o klinické ověření ani záruku úplnosti nad libovolnou odpovědí.

Pro kontrolu záměn, negací, subjektu, času, překlepů a pokynů vložených do odpovědi
je samostatná sada s povolenými tématy a kontrolou faktů:

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake.evaluate_topics --cases tests/fixtures/master_precision_cases.json --output .scratch/master-precision.json
```

Parametr `--cases` lze opakovat a spojit obě sady v jediném reportu.

`topic_recall` měří zachycení očekávaných témat. `topic_precision` měří podíl
povolených témat mezi vrácenými pouze u případů s úplným seznamem povolených
témat; stará sada minimálního pokrytí nemá tento jmenovatel. Negace a subjekt
se kontrolují zvlášť. Report ukládá také `api_usage` přímo z brány.

Konečná varianta 16. 10. 2026 prošla spojenou sadou 68/68 případů:
74/74 očekávaných témat zachyceno, v 15 přísně označených případech
19/19 přiřazení povolených, kontroly negací, subjektu a hodnot prošly.
U sady minimálního pokrytí zůstalo 8 souvisejících přiřazení navíc; její
výsledky samy přesnost neurčují. Dalších 9 živých cílených scénářů prošlo.
Jde o malé syntetické sady; větší nezávislé ověření celého rozhovoru zbývá.

## Spotřeba tokenů

MASTER stále posílá všech 49 témat i přesné texty otázek a možností.
Modelová reprezentace vynechává technická metadata pořadí a větvení,
která zpracovává Python; společné poznámky formuláře jsou jen jednou.
Katalog stojí před proměnlivou zprávou, JSON pro API nemá zbytečné mezery.
Cílený extraktor vybírá nejvýše tři příklady: nejprve pro stejnou otázku,
potom pouze stejný typ (`MAX_TARGETED_EXAMPLES` v client.py).
Po vyčerpání rozpočtu kontaktu se další cílená extrakce nespustí.

Měření přes bránu 16. 10. 2026 na stejných syntetických vstupech:

| Požadavek | Před úpravou | Po úpravě | Úspora vstupních tokenů |
| --- | ---: | ---: | ---: |
| MASTER | 16 169 | 11 605 | 28,2 % |
| Cílená únava | 5 598 | 2 457 | 56,1 % |

Jde o dva konkrétní požadavky, nikoli průměr všech kontaktů ani úsporu ceny.
Výstupní tokeny, cache a skutečný tarif se liší. `Client(on_usage=callback)`
volitelně hlásí vstupní/výstupní tokeny, cache, reasoning a dobu volání;
chybějící údaj je null, ne nula. Callback dostává pouze metriky, bez klíče
a textu pacienta. Při testování nastavte callback přes
`dataclasses.replace(Client.from_env(), on_usage=callback)`.

Statický prefix připravuje požadavky pro opakované použití cache podle
[official OpenAI documentation](https://developers.openai.com/api/docs/guides/prompt-caching).
Účinek na konkrétní bráně ověřuje `cached_tokens`; cache ani slevu nepředpokládáme.
Katalog i zpráva zůstávají ve stejném uživatelském vstupu: během ověření se
ukázalo, že přesun katalogu do samostatné systémové části může u citlivého
screeningu vyvolat blokaci brány. `content_filter` se hlásí výslovně a při
selhání úvodní extrakce se původní zpráva může uložit s `processing_error`.
Obecnou extrakci dalších slovních odpovědí zachováváme, aby se neztratily
nově zmíněné potíže. Potvrzení `ano/ne` a `/moznosti` samy LLM nevolají;
potvrzení může otevřít další otázku, která vlastní extrakci potřebuje.

## Samostatná cílená otázka

```text
uv run --locked --env-file llm_intake/.env python -m llm_intake --question unava --debug
uv run --locked --env-file llm_intake/.env python -m llm_intake --question zvraceni --debug
uv run --locked python -m llm_intake --list
```

Výchozí dotazník je `nezadouci_ucinky`. Pro jiný použijte například
`--questionnaire esas --question unava`. Test únavy: „ne, nejde mi spát“ má
vyvolat doptání. U zvracení odpověď „Za posledních 24 hodin dvakrát“ může
rovnou přejít k potvrzení. JSON se vypíše po potvrzení s `--debug`.
Toto původní CLI navíc vypisuje omezenou triáž; „neurčeno“ u nepokrytých
parametrů neznamená chybu LLM přiřazení.

## Cílené doptání

Když odpověď nestačí k rozlišení možností, stejné LLM volání vrátí jednu krátkou
navazující otázku. CLI ji položí místo opakování původního textu. Model dostává
historii skutečných otázek a odpovědí, takže „ne“ interpretuje vůči správné otázce.
Jakmile lze přiřadit možnost, následuje rovnou potvrzení, bez dalšího doptávání.

Na syntetickém příkladu živě ověřeno:

```text
Pacient: ne, nejde mi spat
Doptání: Zmírní se únava při odpočinku vsedě nebo vleže i bez spánku?
Pacient: Odpočinek bez spánku mi nepomůže, ale únava mě omezuje jen při větší námaze.
         Mytí i vaření zvládám.
K potvrzení: Ne, únava mě však omezuje pouze v náročnějších aktivitách.
```

Výchozí limit jsou dvě doplňující otázky na relaci. Po jejich vyčerpání nebo
při doslovném opakování původní či již položené otázky skončí relace stavem
`unresolved`, bez přiřazené možnosti či barvy, se zachovanými zprávami.
CLI vrací kód 2. Toto je počáteční limit, nikoli optimalizovaný klinický práh.
V CLI jej lze nastavit pomocí `--max-clarifications 2`.
Pacientovy opravy po odmítnutí počítáme zvlášť; každá nejasná oprava ale čerpá
stejný limit doptání. Limit lze změnit v Pythonu přes `max_clarifications`.

### Podobnost, RAG a měření

Pro jednu otázku jsou všechny přípustné možnosti už v promptu. Náš návrh je
proto zatím přímé přiřazení a zjištění chybějícího údaje, bez RAG, embeddingů
a vektorové databáze. Sémantická podobnost slouží k vyhledávání či řazení,
její skóre samo o sobě nedokládá, že text splňuje podmínky konkrétní odpovědi.
Nepoužíváme svévolný práh cosine similarity ani modelovo nekalibrované procento jistoty.

`metrics` měří úspěšná extrakční volání (i nejasná), vydané doplňující otázky,
odmítnutí a nastavený limit. Na samostatných označených scénářích chceme měřit:
správnost nabídnuté možnosti, podíl správně potvrzených relací, počet zbytečných
doptání u dostatečné odpovědi, počet doptání k potvrzení, opravy a nevyřešené relace.
Potvrzení pacientem je uživatelská kontrola, ne nezávislá reference správnosti.
Teprve nad takovou sadou lze vyhodnotit přínos podobnosti a nastavit případný práh.

Zdroje k technickému rozlišení a vyhodnocení:
[OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings),
[Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).
Jde o naše doporučení pro malý počet možností; neprovedli jsme srovnání s RAG.

## Model a API

Výchozí kandidát je **gpt-6.1-sol**. Oficiální OpenAI dokumentace jej doporučuje
pro kompromis schopností a nákladů; podporuje Chat Completions bez nástrojů
a strukturovaný výstup. Pro tuto úlohu využíváme právě extrakci do JSON schématu.
Výběr je výchozí technické doporučení, nikoli výsledek benchmarku v češtině.
GPT-6 Luna je kandidát pro pozdější porovnání na stejných příkladech, GPT-6 Astra
pro náročné případy; první verze neimplementuje automatické přepínání modelů.
Ostatní uvedené modely jsme na tomto úkolu neporovnávali.

Zdroje ověřené 16. 10. 2026: [výběr modelů](https://developers.openai.com/api/docs/models),
[gpt-6.1-sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).
Dokumentace poskytovatele nepotvrzuje konfiguraci naší hackathonové brány.

Adaptér posílá `POST /chat/completions` na dodanou base URL:
`https://apim-rakathon-q7146n.azure-api.net/openai/v1/`.
Používá `response_format=json_schema` se `strict=true`, bez nástrojů a streamování.
Výstup kontroluje i lokálně. Pokud brána schéma nepodporuje, požadavek selže;
nepřecházíme potichu na volný text. Přístupový klíč je pouze v prostředí.

## Spuštění z kořene repa

Python 3.12 + uv. Bez nových závislostí, stejné příkazy na Linuxu i PowerShellu:

```text
uv sync --locked
uv run python -m llm_intake --list
```

Zkopírujte `llm_intake/.env.example` do `llm_intake/.env` a lokálně v něm
nastavte klíč. `.env` ignoruje Git. Pak:

```text
uv run --env-file llm_intake/.env python -m llm_intake --question unava
uv run --env-file llm_intake/.env python -m llm_intake --questionnaire bolest_analgeticka_terapie --question sos
```

`MEDDI_LLM_MODEL` označuje **deployment**, nikoli obecný název modelu:
`gpt-6-1-sol-dz-eu` (model gpt-6.1-sol). Pro dodanou bránu je ověřená
autentizace `MEDDI_LLM_KEY_HEADER=api-key`. Klíč se posílá bez prefixu Bearer.
Adaptér nadále umožňuje explicitně zvolit `Authorization` nebo
`Ocp-Apim-Subscription-Key` pro jiné konfigurace, ale tato brána je nepřijala.

Ověřeno 16. 10. 2026: `Authorization` i `Ocp-Apim-Subscription-Key` vracely
401 s chybějícím subscription key. `api-key` autentizaci opravilo; původní
`gpt-6.1-sol` poté vracelo 404 `DeploymentNotFound`. S přesným deploymentem
`gpt-6-1-sol-dz-eu` proběhla extrakce se striktním schématem úspěšně.
Obecné vysvětlení této vrstvy autentizace:
[Azure API Management 401](https://learn.microsoft.com/en-us/troubleshoot/azure/api-mgmt/availability/unauthorized-errors-invoke-apis).

Odpovězte volným textem, zkontrolujte přehled a zadejte `ano` nebo `ne`.
Příkaz `/moznosti` bez volání LLM vypíše texty možností, pokud Vám to usnadní
odpověď. Následně lze zadat název nebo slovní výběr více možností; indexy
a barvy pacientovi nezobrazujeme. Nabídka není povinná.
Po `ne` napište opravu; potom se znovu potvrzuje celá aktuální odpověď.
`/konec`, Ctrl+C nebo konec vstupu ukončí relaci. Interní JSON ani barvy se
v běžném pacientském průchodu nezobrazují. Pro vývojářské ověření přidejte
`--debug`; teprve tehdy se po potvrzení vypíše JSON. Modul ho nikam automaticky
neukládá. Po potvrzení je relace uzavřená.

```text
uv run --env-file llm_intake/.env python -m llm_intake --question unava --debug
```

První ověření s klíčem proveďte na syntetické odpovědi k únavě, například
„Odpočinek mi pomůže.“ a následné opravě „Nepomůže, ale omezuje mě jen při sportu.“

## Python rozhraní pro kolegy

```python
from llm_intake import Intake, load_question
from llm_intake.client import Client

session = Intake(
    load_question("nezadouci_ucinky", "unava"), Client.from_env(), max_clarifications=2
)
draft = session.submit("Odpočinek mi pomůže.")  # validovaný návrh, confirmed=False
print(session.patient_summary())  # hodnoty přeložené texty definic

# Volající musí obdržet explicitní potvrzení od pacienta:
confirmed = session.confirm()  # confirmed=True
# Alternativně po odmítnutí: session.reject(); session.submit("Oprava: …")
```

`Intake` přijímá funkci `extract(question, source_messages, source_questions) -> dict`.
`Client` je jeden adaptér této funkce; pro testování se nahrazuje funkcí bez sítě.
Kolegové se mohou napojit na export, aniž by používali CLI nebo konkrétní API.
Je-li `state == "needs_answer"`, další otázku poskytuje `session.next_question`;
odpověď se opět předá do `submit()`. Potvrdit lze jen `needs_confirmation`.

Výstup `snapshot()` / `confirm()` má **`schema_version=2`**, `dotaznik_id`,
`otazka_id`, původní `otazka`, `revision`, `state`, `confirmed`, `odpoved`,
`odpoved_index`, `extraction`, `source_messages` a `signaly_odpovedi`. Indexy jsou od nuly,
stejně jako `odpoved_index` v dodaných check-inech. Jedna možnost je celé číslo,
více možností seznam; u škály, čísla a textu je `odpoved_index=null`.
`odpoved` obsahuje text možnosti / seznam textů nebo přímo číslo či text.
Verze 2 přidává `source_questions` (stejné pořadí jako `source_messages`),
`follow_up` (další otázka při `needs_answer`), `unresolved_reason` a `metrics`.
Při migraci vlastního extraktoru přidejte třetí argument a nové pole `follow_up`;
u přiřazené odpovědi je null, u nejasné povinná jedna otázka do 240 znaků.

`signaly_odpovedi` obsahují položky `odpoved_index` a `barva` převzaté kódem
z definic vybraných možností. Model barvu neurčuje ani ji nedostává na vstupu.
U možností bez barvy je `barva=null`; u nejasné odpovědi nebo typu bez možností
je seznam prázdný. Tato barva je původní signál odpovědi, **nikoli výsledná
úroveň triáže** (zdroj: README datového balíčku, oddíl 4, „Dotazníky“).

`extraction` obsahuje pouze `status` (`answered` / `unclear`), `value`,
`source_index`, doslovnou citaci `evidence` a `follow_up`. Nejasná odpověď má
hodnotu a zdroj null a obsahuje cílené doptání; není v ní domyšlená volba.
Zdrojový index ukazuje do `source_messages`. Citace umožní dohledání zdroje,
ale její existence ani validní schéma nedokazují správnou interpretaci.

Při odmítnutí nelze starý návrh potvrdit ani exportovat přes `confirmed_data()`.
Při chybě API nebo validace se stav nezmění; opravu lze zkusit znovu.
`snapshot()` je i pro návrhy a vždy obsahuje stav potvrzení. Při budoucím
napojení triáže je třeba vyhodnocovat urgentní signály také před potvrzením;
tento izolovaný modul upozorňování neimplementuje a nesmí být jeho jedinou bránou.

## Prompt a omezení první verze

- [prompt.md](prompt.md): instrukce pro extrakci, negace, nejasnost a opravy.
- [examples.json](examples.json): banka třinácti syntetických příkladů pro in-context learning;
  do cíleného požadavku vstupují nejvýše tři relevantní,
  včetně výběru více účinků a „žádné“. U otázky drží jen dvojici ID; klient
  doplní aktuální text, návod i všechny možnosti ze stejných definic.
  Posílají se v každém požadavku; model se tím trvale nepřetrénovává.
- Stav a zdrojové odpovědi drží Python v paměti. Do dalšího volání posílá
  definici jedné otázky a dosavadní otázky i odpovědi k ní, nikoli celou kartu pacienta.
- Otázky se čtou z dodaného `dotazniky_definice.json`. Barvy a upozornění
  se modelu neposílají. Balíček zachovává také pořadí, `podminka` a směr škály
  z poznámky dotazníku; popis barev z této poznámky se vynechává.
  CLI volí jednu otázku explicitně. Python `QuestionnaireFlow` už umí pořadí
  a větvení celého formuláře nebo vybrané větve; `MasterDialogue` nad ním
  řídí kandidáty a potvrzování v rámci jednoho omezeného kontaktu.
- Typy `jedna`, `vice`, `skala_1_10`, `cislo`, `text` mají lokální validaci.
  U `nrs` text otázky uvádí 0–10, ale typ a poznámka definují 1–10. Prototyp
  respektuje 1–10 a nulu nesmí přemapovat na jedničku; rozsah potvrdit s mentorem
  (zdroj: definice dotazníků, `bolest_analgeticka_terapie/nrs`).
- Zpráva může obsahovat další důležité údaje, které se do této jedné odpovědi
  nevejdou. Zůstává v `source_messages`; obecná extrakce klinických pozorování
  je další krok a tento export ji nenahrazuje.

## Kontroly

```text
uv run python -m pytest tests/test_llm_intake.py -q
uv run python -m pytest tests/test_master_contract.py tests/test_questionnaire_flow.py -q
uv run ruff check llm_intake tests
```

Automatické testy používají náhradu modelu a HTTP transportu. Ověřují potvrzování,
opravy, validaci, pacientský výpis bez možností a barev, mapování interního signálu
a chyby API. Vedle nich proběhlo živé ověření na syntetické odpovědi; nenahrazuje
systematické měření kvality extrakce v češtině a slovenštině.
