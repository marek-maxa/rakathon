# LLM intake: jedna otázka a potvrzení

Samostatný modul pro první experimenty. Pacient vidí otázku a odpovídá vlastními
slovy. LLM sémanticky přiřadí odpověď k možnosti z interních definic a pacient
potvrdí její slovní znění. Nabídka možností se pacientovi předem nezobrazuje.
Při odmítnutí přijme opravu a celý cyklus zopakuje. Nemění pacientská data,
nečte reference, neprovádí triáž a nespravuje kartu ani časování kontaktů.

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

session = Intake(load_question("nezadouci_ucinky", "unava"), Client.from_env(), max_clarifications=2)
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
- [examples.json](examples.json): jedenáct syntetických příkladů pro in-context learning.
  Posílají se v každém požadavku; model se tím trvale nepřetrénovává.
- Stav a zdrojové odpovědi drží Python v paměti. Do dalšího volání posílá
  definici jedné otázky a dosavadní otázky i odpovědi k ní, nikoli celou kartu pacienta.
- Otázky se čtou z dodaného `dotazniky_definice.json`. Barvy a upozornění
  se modelu neposílají. Jedna otázka se volí explicitně; podmínky `podminka`
  a průchod celým dotazníkem patří do pozdější orchestrace.
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
uv run ruff check llm_intake tests/test_llm_intake.py
```

Automatické testy používají náhradu modelu a HTTP transportu. Ověřují potvrzování,
opravy, validaci, pacientský výpis bez možností a barev, mapování interního signálu
a chyby API. Vedle nich proběhlo živé ověření na syntetické odpovědi; nenahrazuje
systematické měření kvality extrakce v češtině a slovenštině.
