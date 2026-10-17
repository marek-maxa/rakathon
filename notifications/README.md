# SMTP demo

Samostatná Flask aplikace odešle na ručně zadanou adresu pevný předmět a text
z `app.py`. Nečte pacientská data a není napojená na triáž. Transport lze
později využít za předávacím adaptérem; klinická fronta, priority, opakování
a převzetí jsou úkoly [K6](../docs/meddi-onco-plan.md#implementační-kroky-a-závislosti).

Zkopírujte [.env.example](.env.example) do `notifications/.env` a nastavte
SMTP server, povoleného odesílatele a případné přihlašovací údaje.
`SMTP_SECURITY=starttls` používá výchozí port 587, `ssl` port 465.
Uživatelské jméno a heslo musí být obě vyplněná nebo obě prázdná; druhá
varianta vyžaduje SMTP server umožňující neautentizované odeslání přes TLS.

Z kořene repozitáře, Linux i PowerShell:

```text
uv run --locked --env-file notifications/.env python -m flask --app notifications.app run --port 5001
```

Otevřete http://127.0.0.1:5001. Port 5001 umožní souběh s pacientským webem
na 5000. Při přímém `python notifications/app.py` aplikace používá výchozí
port 5000 a prostředí je třeba načíst přes `uv run --env-file` jako výše.

Formulář používá CSRF token a validaci adresy. Úspěch znamená přijetí SMTP
serverem, nikoli doručení do schránky nebo převzetí zdravotníkem. Lokální
`.env` ignoruje Git. Automatické testy SMTP transportu a tohoto formuláře
zatím chybí; `tests/test_notifications.py` v repozitáři neexistuje. Jejich
doplnění s náhradou SMTP bez skutečného odesílání evidují [úkoly](../docs/tasks.md).

## Pravidelné pozvánky

Minimální plánovač používá stejný SMTP transport a uložený kontakt pacienta.
Nastavení intervalu, jednu připomínku, prohlížení/zrušení plánu a periodické
spouštění popisuje [architektura](../docs/architecture.md#minimální-plánovač-notifikací).
Nezapíná se automaticky spuštěním webu. Medicínské intervaly nejsou přednastavené.
