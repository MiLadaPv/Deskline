# Подпись Windows Setup — гайд для новичка

Цель: чтобы при скачивании `DesklineSetup-*.exe` Windows не пугал надписью  
«Неизвестный издатель» / SmartScreen.

Без сертификата **нельзя** закончить этот шаг «только кодом» — нужен платный  
Authenticode-сертификат на юрлицо/ИП (AndalusGames).

---

## Что такое OV и EV (простыми словами)

| Тип | Что даёт | Сложность | Ориентир цены |
|-----|----------|-----------|----------------|
| **OV** (Organization Validation) | Имя компании в подписи | Средняя: проверяют компанию | обычно $200–400 / год |
| **EV** (Extended Validation) | Строже проверка + лучше репутация SmartScreen | Выше (часто USB-токен / HSM) | обычно $300–600+ / год |

Для старта Deskline достаточно **OV Code Signing**.  
EV — если готовы платить и возиться с токеном ради более быстрой «зелёной» репутации.

**Важно:** сертификат покупается на **организацию** (AndalusGames), не на личный Gmail «как для сайта HTTPS».  
Нужны: регистрация компании/ИП, адрес, часто паспорт директора, иногда звонок/email на корпоративный домен.

---

## План из 6 шагов

```
1. Купить OV Code Signing
2. Установить сертификат на ПК для релизов
3. Поставить Windows SDK (signtool)
4. Собрать Setup: prepare_release.ps1
5. Подписать: sign_release.ps1
6. Выложить на GitHub Releases
```

---

## Шаг 1 — Купить сертификат

Популярные продавцы (Code Signing / Authenticode):

1. [SSL.com](https://www.ssl.com/) — часто проще для старта  
2. [Sectigo](https://sectigo.com/)  
3. [DigiCert](https://www.digicert.com/)  
4. Альтернатива без USB: **[Azure Trusted Signing](https://learn.microsoft.com/en-us/azure/trusted-signing/)** (облачная подпись Microsoft; своя регистрация Azure)

На сайте выберите продукт с названием вроде:

- **Code Signing Certificate**  
- **OV Code Signing**  
- не «SSL/TLS для сайта» и не «email S/MIME»

После оплаты вас попросят пройти **валидацию организации** (документы).  
Это занимает от нескольких часов до нескольких дней — нормально.

В конце вы получите либо:

- файл `.pfx` / `.p12` + пароль, либо  
- установку через браузер в хранилище Windows, либо  
- доступ к облачной подписи (Azure / token).

**Никогда не коммитьте `.pfx` и пароли в git.**

---

## Шаг 2 — Установить сертификат на ПК

### Вариант A — файл `.pfx`

1. Скопируйте `.pfx` в безопасное место (не в репозиторий Deskline).  
2. Двойной клик → мастер импорта → **Current User** → введите пароль.  
3. Отметьте «Mark this key as exportable» только если понимаете риск.  
4. Готово, когда в сертификатах видна ваша компания.

Проверка в PowerShell:

```powershell
Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.HasPrivateKey } |
  Select-Object Subject, NotAfter, Thumbprint
```

Должна быть строка с `AndalusGames` (или вашим юр. именем) и `Thumbprint`.

### Вариант B — Azure Trusted Signing

Следуйте Microsoft docs; подпись идёт через их endpoint, не через локальный `.pfx`.  
Для новичка OV + `.pfx` обычно проще один раз понять.

---

## Шаг 3 — Установить `signtool`

1. Установите **[Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/)**  
   (достаточно компонента «Windows SDK Signing Tools»).  
2. Или Visual Studio Installer → Individual components → **Windows SDK**.

Найдите `signtool.exe`, обычно путь вида:

```text
C:\Program Files (x86)\Windows Kits\10\bin\10.0.XXXXX.0\x64\signtool.exe
```

Проверка:

```powershell
Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter signtool.exe |
  Select-Object -First 3 FullName
```

Скрипт `scripts/sign_release.ps1` ищет `signtool` сам.

Также нужен **Inno Setup 6** для сборки Setup (уже используется в `build_installer.ps1`).

---

## Шаг 4 — Собрать релиз (без подписи)

В PowerShell из корня проекта:

```powershell
cd D:\Projects\Deskline
powershell -ExecutionPolicy Bypass -File scripts\prepare_release.ps1
```

Что произойдёт:

1. тесты  
2. zip расширения → `release\Deskline-Extension-<ver>.zip`  
3. сборка Tauri + PyInstaller + Inno → `release\DesklineSetup-<ver>.exe`  
4. файл `release\SHA256SUMS.txt` (пока для **неподписанных** файлов)

Сборка может занять 5–20 минут. Если упадёт на Inno — установите [Inno Setup 6](https://jrsoftware.org/isinfo.php).

Пока Setup **не подписан** — его ещё не выкладывайте как «официальный» публичный билд (можно тестировать сами).

---

## Шаг 5 — Подписать

Когда сертификат уже в Windows и `signtool` есть:

```powershell
cd D:\Projects\Deskline
powershell -ExecutionPolicy Bypass -File scripts\sign_release.ps1
```

Скрипт:

1. найдёт свежий `DesklineSetup-*.exe`  
2. по возможности подпишет `dist\Deskline\Deskline.exe` и `deskline-desktop.exe`  
3. подпишет Setup  
4. проверит подпись (`signtool verify`)  
5. пересчитает `SHA256SUMS.txt`

Если сертификатов несколько:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sign_release.ps1 -Thumbprint "ВАШ_THUMBPRINT"
```

Thumbprint возьмите из шага 2 (без пробелов).

Ручная команда (если скрипт не подходит):

```powershell
& "C:\Program Files (x86)\Windows Kits\10\bin\<ver>\x64\signtool.exe" sign `
  /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /a `
  "D:\Projects\Deskline\release\DesklineSetup-0.5.30.exe"

& "C:\Program Files (x86)\Windows Kits\10\bin\<ver>\x64\signtool.exe" verify /pa /v `
  "D:\Projects\Deskline\release\DesklineSetup-0.5.30.exe"
```

`/tr` — **timestamp**: подпись останется валидной после истечения сертификата.

---

## Шаг 6 — Выложить на GitHub

Нужен [GitHub CLI](https://cli.github.com/) (`gh auth login`) или загрузка руками на сайте.

```powershell
cd D:\Projects\Deskline
$ver = (python -c "from deskline import __version__; print(__version__)").Trim()
gh release create "v$ver" `
  "release/DesklineSetup-$ver.exe" `
  "release/Deskline-Extension-$ver.zip" `
  "release/SHA256SUMS.txt" `
  -t "Deskline v$ver" `
  -F docs/RELEASE_NOTES.template.md
```

Проверьте: https://github.com/MiLadaPv/Deskline/releases/latest  

Кнопка «Скачать» на `/welcome` уже ведёт туда.

---

## Что будет после первой публикации

- Первые дни SmartScreen **всё ещё может** предупреждать — у нового издателя мало «репутации».  
- EV и частые скачивания ускоряют доверие; OV со временем тоже «прогревается».  
- Не переподписывайте каждый день разными сертификатами без нужды.

---

## Частые ошибки

| Симптом | Что делать |
|---------|------------|
| `signtool` not found | Установить Windows SDK, перезапустить PowerShell |
| No certificates found | Импортировать `.pfx`, проверить `Cert:\CurrentUser\My` |
| Access denied / private key | Импорт не туда / нет прав на ключ — переимпорт |
| Timestamp failed | Сеть/файрвол; попробуйте другой `/tr` (sectigo, digicert) |
| Inno / Tauri build fail | Отдельно починить `build_installer.ps1`, потом снова prepare |

---

## Минимальный чеклист «я новичок и хочу закончить»

1. [ ] Куплен **OV Code Signing** на AndalusGames  
2. [ ] `.pfx` импортирован, в `Cert:\CurrentUser\My` есть Thumbprint  
3. [ ] Установлены Windows SDK + Inno Setup 6  
4. [ ] `prepare_release.ps1` создал `release\DesklineSetup-*.exe`  
5. [ ] `sign_release.ps1` прошёл `verify`  
6. [ ] GitHub Release с тремя файлами опубликован  

Когда дойдёте до шага 1 (купили сертификат) или шага 2 (есть `.pfx`) — напишите, на каком вы этапе: подскажу точные команды под ваш случай (pfx / Azure / несколько сертификатов).
