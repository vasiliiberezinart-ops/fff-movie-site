# FFF-Movie — мини-платформа для двух фильмов

5€ за фильм, 48ч доступ, Stripe + PayPal, lo-fi доставка приватной ссылки на email.

## Локально

```bash
cd ~/Desktop/cinema-platform
python3 -m http.server 8765
# открыть http://localhost:8765/
```

## Что сделано

- `index.html` — главная: hero с teaser-видео + 2 карточки фильмов
- `films/seven.html` — детальная страница «Seven» (Шерлок / Кукушкин / Малкович)
- `films/freedom-friends.html` — детальная страница «Freedom Friends»
- `success/index.html` — страница после оплаты Stripe
- `styles.css` — палитра Pantone Autumn-Winter 2025/2026:
  - French Roast `#1a100c` (фон) · Hot Chocolate `#3a241c` (поверхность)
  - Damson `#5d2a3a` (бордо акцент) · Brandied Melon `#c77752` (CTA)
  - Bright White `#f4ede3` (текст)
- Шрифты: Cormorant Garamond (винтаж) + Inter (модерн)
- Эффект киноплёнки (SVG-grain overlay, 5% opacity)
- Постеры-плейсхолдеры — заменить на реальные кадры

## Что нужно от Васи

### 1. Название платформы
Сейчас стоит `FFF-Movie` — заменю одной командой `sed` когда скажешь финальное.

### 2. Stripe Payment Links
Создай два Payment Link в Stripe Dashboard (5€ each), вставлю в:
- `films/seven.html`: `STRIPE_PAYMENT_LINK_SEVEN`
- `films/freedom-friends.html`: `STRIPE_PAYMENT_LINK_FREEDOM_FRIENDS`

В каждом Payment Link → Settings → After payment → Redirect to:
`https://YOUR-DOMAIN/success/`

### 3. PayPal
Либо `paypal.me/yourhandle/5` ссылка, либо PayPal hosted button.
Поставлю в те же файлы вместо `PAYPAL_ME_OR_HOSTED_BUTTON_*`.

### 4. Материалы
Положи в `assets/raw/`:
- `fff_teaser.mp4` — teaser для hero (можно 30-60с loop)
- `seven_full.mp4` или ссылку на private Vimeo
- `freedom-friends_full.mp4` или ссылку на private Vimeo

После этого я нарежу 6-9 кадров на постеры/stills через ffmpeg
и заменю плейсхолдеры на реальные кадры.

### 5. Vimeo private (для доставки)
- Загрузи фильм на Vimeo, поставь Privacy: «only people with the private link»
- Privacy → Embed: «Specific domains» → твой домен
- Когда Stripe пришлёт уведомление об оплате — отправляешь покупателю email
  с приватной ссылкой и говоришь «активна 48ч с момента открытия»

### 6. Email для уведомлений
Сейчас в коде стоит `vasiliyberezin.art@gmail.com` — замени на свой.

## Деплой на GitHub Pages

```bash
cd ~/Desktop/cinema-platform
git init
git add -A
git commit -m "fff-movie: initial cinema platform"
gh repo create vasiliiberezinart-ops/fff-movie-site --public --source=. --push
# в Settings → Pages → main / root → save
```

Если есть свой домен (например `fff-movie.com`):
- Settings → Pages → Custom domain
- DNS: A-записи на GitHub Pages IP

## Палитра (откуда)

belt-magazine «Цвета осень-зима 2025/2026 — новая гармония» —
Pantone autumn-winter palette: French Roast / Hot Chocolate / Damson /
Brandied Melon / Bright White. Винтаж (Hot Chocolate, Damson) +
живой акцент (Brandied Melon) — «под старину с новым уклоном».

## Дальше (когда захочешь)

- Автоматическая доставка через Vimeo OTT (платно, ~$1/sub) или Cloudflare Stream + Workers
- Подписка 5€/мес когда будет 5+ фильмов
- Multi-language (RU / EN / FR) — у тебя аудитория полиглот
- Новостная рассылка на новые релизы
