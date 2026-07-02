# ☀️ LINE Good-Morning Weather Bot

Every morning at **7:00 AM (Taipei time)**, this bot pushes a good-morning greeting and a
weather-card picture for **新北市 New Taipei City** into your LINE group chat.

How it works:

```
GitHub Actions (daily 07:00 Taipei cron)
   → fetch weather from Open-Meteo (free, no API key)
   → render a PNG weather card with Pillow
   → commit the PNG to this repo (raw.githubusercontent.com hosts it over HTTPS)
   → call LINE Messaging API "push message" with a text + image message
```

LINE image messages require a **public HTTPS URL** — a LINE bot cannot "upload" an image
directly. Committing the image to a **public** GitHub repo is the zero-cost way to host it.

---

## Part 1 — Create the LINE bot (~10 minutes)

1. Go to the [LINE Developers Console](https://developers.line.biz/console/) and log in
   with your LINE account.
2. Create a **Provider** (any name, e.g. "Max"), then create a **Messaging API channel**.
   - Since 2024 this flow routes you through creating a **LINE Official Account** first —
     just follow the prompts, then in the [Official Account Manager](https://manager.line.biz/)
     go to **Settings → Messaging API** and enable it, choosing the provider you created.
3. Back in the LINE Developers Console, open your channel → **Messaging API** tab →
   scroll to **Channel access token (long-lived)** → click **Issue**.
   📋 Save this token — it becomes the `LINE_CHANNEL_ACCESS_TOKEN` secret.

### Allow the bot to join group chats

4. In [LINE Official Account Manager](https://manager.line.biz/) → your account →
   **Settings (設定) → Account settings → Features**: set **Group chats (加入群組或多人聊天室)**
   to **Allow**.
5. (Recommended) In **Response settings (回應設定)**, turn **off** auto-reply messages so the
   bot doesn't spam the group when people chat.

### Get the group ID

The group ID isn't shown anywhere in the LINE app — the bot learns it from a webhook event
when it's invited to the group. You don't need a server; a webhook-viewer site works:

6. Go to <https://webhook.site> — it gives you a unique URL like
   `https://webhook.site/xxxx-xxxx...`. Keep the tab open.
7. In the LINE Developers Console → **Messaging API** tab:
   - Set **Webhook URL** to that webhook.site URL and click **Verify**.
   - Turn **Use webhook** ON.
8. In the LINE app, **invite your bot into the group chat** (add it as a friend first using
   the QR code on the Messaging API tab, then invite it to the group).
9. Watch the webhook.site tab: a `join` event appears. In its JSON body find:
   ```json
   "source": { "type": "group", "groupId": "Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" }
   ```
   📋 Save that `Cxxxx...` value — it becomes the `LINE_GROUP_ID` secret.
   (If no event shows up, just send any message in the group — a `message` event will
   appear with the same `groupId`.)
10. You can now turn **Use webhook** OFF again — the daily push doesn't need it.

---

## Part 2 — Set up the GitHub repo (~5 minutes)

1. Create a **new public repo** on GitHub (e.g. `line-weather-bot`).
   ⚠️ It must be **public**, because `raw.githubusercontent.com` only serves files from
   public repos without authentication — that's how LINE fetches the image. Only the
   weather pictures are stored there; your token and group ID stay in encrypted secrets.
2. Upload these files to the repo (keeping the folder structure):
   ```
   morning_weather.py
   requirements.txt
   .github/workflows/daily-weather.yml
   ```
3. In the repo: **Settings → Secrets and variables → Actions → New repository secret**,
   add both:
   | Name | Value |
   |---|---|
   | `LINE_CHANNEL_ACCESS_TOKEN` | the long-lived token from Part 1 step 3 |
   | `LINE_GROUP_ID` | the `Cxxxx...` ID from Part 1 step 9 |
4. In the repo: **Settings → Actions → General → Workflow permissions** →
   select **Read and write permissions** (the workflow commits the daily image).

### Test it

Go to the **Actions** tab → **Daily good-morning weather** → **Run workflow**.
Within a minute your LINE group should receive the greeting + weather card. 🎉

After that it runs automatically every day. (GitHub schedules are in UTC — `0 23 * * *`
is 7:00 AM Taipei. GitHub sometimes delays cron jobs by a few minutes.)

---

## Costs and limits

- **Open-Meteo**: free, no API key, fine for one request per day.
- **GitHub Actions**: free for public repos.
- **LINE**: the free plan includes **200 messages/month**, and a push to a group is
  counted **once per group member**. Example: a 5-person group × 31 days ≈ 155
  messages/month — OK. A group larger than ~6 people will exceed the free tier;
  check your count in [LINE Official Account Manager](https://manager.line.biz/).
  (The text + image sent together count as **one** message, not two.)

## Customizing

- **City**: edit `CITY_NAME_ZH / CITY_NAME_EN / LATITUDE / LONGITUDE` at the top of
  `morning_weather.py`.
- **Send time**: edit the cron line in `.github/workflows/daily-weather.yml`
  (remember it's UTC: Taipei time − 8 hours).
- **Greetings**: edit the `GREETINGS` list — one is picked at random each day.
- **Card look**: colors are in `THEMES`, layout in `generate_card()`.

## Test locally without sending

```bash
pip install requests pillow
python morning_weather.py generate     # writes images/weather-YYYY-MM-DD.png
```
