# JEE Prep Hub Telegram Bot — Mission Control

A standalone Telegram bot with its own Supabase data model. It does **not** call the JEE Prep Hub website.

## Signature features in this starter
- **Mission Mode:** daily study mission and XP rewards.
- **Mistake Memory:** missed quiz questions are saved for later review.
- **Backlog Rescue:** capture backlog tasks and mark them complete.
- **Quick Quiz:** four-option questions, explanations, attempt history, basic accuracy.
- **Resource Universe:** publish official/authorized resource links.
- **Progress:** XP, level, question accuracy, and open mistake count.

This is a functional starter, not a finished production platform. It does not yet include AI chat, battle matchmaking, scheduled reminders, or an admin dashboard.

## 1. Create Telegram bot
1. Open Telegram and message `@BotFather`.
2. Run `/newbot`, choose a display name and username.
3. Copy the bot token. Keep it private.

## 2. Set up Supabase
1. Open your Supabase project.
2. Go to **SQL Editor**.
3. Review `supabase_schema.sql`, then run it.
4. Add a few questions to `quiz_questions` and authorized links to `resource_links`.

Example question (run in SQL Editor after schema setup):
```sql
insert into public.quiz_questions
(subject, topic, difficulty, question, options, correct_index, explanation, is_active)
values
('Physics', 'Kinematics', 'easy',
 'A body starts from rest and accelerates uniformly at 2 m/s². Its speed after 3 s is:',
 '["3 m/s","6 m/s","9 m/s","12 m/s"]'::jsonb,
 1,
 'Use v = u + at = 0 + 2×3 = 6 m/s.',
 true);
```

Example approved resource:
```sql
insert into public.resource_links (title, subject, topic, url, description, is_published)
values ('NCERT Physics', 'Physics', 'Reference', 'https://ncert.nic.in/', 'Official NCERT website', true);
```

## 3. Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Fill `.env` with the Telegram token, Supabase URL, and **service-role key** from Supabase project settings. The service-role key is server-only. Never commit `.env`, send it in chat, or put it in browser/frontend code.

Then run:
```bash
python bot.py
```

## 4. Push to GitHub
Create a private repository, upload these files, and ensure `.env` is not uploaded. This folder contains no secret credentials.

## 5. Hosting
The included `render.yaml` is a starting point for a background worker. Free hosting policies can change and may sleep, suspend, or require a paid plan; verify the current terms before relying on it. Add the three environment variables in the host dashboard.

## Security notes
- This bot is independent of the website and uses Telegram IDs for bot-only profiles.
- The SQL schema enables RLS and intentionally creates no public policies.
- Keep the service-role key only in the server's environment.
- Only add resources you own or have permission to distribute/link.
- Before a public launch, add rate limiting, admin-only resource/question management, error handling, monitoring, backups, and privacy/deletion commands.
