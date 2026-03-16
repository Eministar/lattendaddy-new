# Website SQL Reference

Diese Datei ist für den Web-Entwickler gedacht. Die Queries orientieren sich an der aktuellen Starry-Datenbankstruktur.

Hinweise:
- `:guild_id`, `:week_key`, `:month_key` sind Platzhalter und müssen an den eingesetzten SQL-Client angepasst werden.
- Für `Parlament` liegen Namen, Handles, Avatare und Partei-Logos jetzt direkt in SQL-Snapshots.
- Für `Aktivster User`, `Flaggenkönig` und `Geburtstagskind` kommt weiterhin primär die `user_id` aus SQL; Name/Avatar kann die Website bei Bedarf separat anreichern.

## 1. Aktivster User im letzten Monat

Der Bot schreibt pro Nachricht zusätzlich in `user_stats_monthly`. Damit kann die Website den aktivsten User pro Kalendermonat direkt aus SQL holen.

Zusätzlich wird beim ersten Start nach diesem Schema-Upgrade einmalig der vorhandene Gesamtstand aus `user_stats` in den aktuellen Monat übernommen, damit die Karte nicht bei `0` startet.

```sql
SELECT
  user_id,
  month_key,
  message_count,
  last_message_at
FROM user_stats_monthly
WHERE guild_id = :guild_id
  AND month_key = :month_key
  AND message_count > 0
ORDER BY message_count DESC, last_message_at ASC, user_id ASC
LIMIT 1;
```

Falls ihr eine Rangliste für den Monat braucht:

```sql
SELECT
  user_id,
  month_key,
  message_count,
  last_message_at
FROM user_stats_monthly
WHERE guild_id = :guild_id
  AND month_key = :month_key
  AND message_count > 0
ORDER BY message_count DESC, last_message_at ASC, user_id ASC
LIMIT 25;
```

## 2. Flaggenkönig

Der aktuelle Flaggenkönig im Bot läuft über die Wochenwertung nach Punkten.

Passend zur Bot-Logik:

```sql
SELECT
  user_id,
  weekly_points,
  correct,
  wrong,
  current_streak,
  best_streak
FROM flag_quiz_players
WHERE guild_id = :guild_id
  AND weekly_key = :week_key
  AND weekly_points > 0
ORDER BY weekly_points DESC, correct DESC, updated_at ASC
LIMIT 1;
```

Falls ihr stattdessen Monats- oder Alltime-Karten braucht:

```sql
SELECT
  user_id,
  monthly_points,
  correct,
  wrong,
  current_streak,
  best_streak
FROM flag_quiz_players
WHERE guild_id = :guild_id
  AND monthly_key = :month_key
  AND monthly_points > 0
ORDER BY monthly_points DESC, correct DESC, updated_at ASC
LIMIT 1;
```

```sql
SELECT
  user_id,
  total_points,
  correct,
  wrong,
  current_streak,
  best_streak
FROM flag_quiz_players
WHERE guild_id = :guild_id
  AND total_points > 0
ORDER BY total_points DESC, correct DESC, updated_at ASC
LIMIT 1;
```

## 3. Geburtstagskind / Geburtstagskinder heute

Für die Website sollte die Guild-spezifische Tabelle `birthdays_current` verwendet werden. Diese wird vom Bot täglich aktualisiert.

Alle Geburtstagskinder heute:

```sql
SELECT
  user_id,
  day,
  month,
  year,
  date_value
FROM birthdays_current
WHERE guild_id = :guild_id
ORDER BY user_id ASC;
```

Falls nur das erste Geburtstagskind für eine einzelne Hero-Card gebraucht wird:

```sql
SELECT
  user_id,
  day,
  month,
  year,
  date_value
FROM birthdays_current
WHERE guild_id = :guild_id
ORDER BY user_id ASC
LIMIT 1;
```

## 4. Parlamentsabgeordnete

Der Bot synchronisiert den aktuellen sichtbaren Parlamentsstand jetzt nach jedem Panel-Refresh in `parliament_current_members`. Die Website kann also 1:1 aus SQL rendern, ohne die Live-Discord-Rollen selbst nachzubauen.

```sql
SELECT
  section_key,
  section_label,
  section_order,
  slot_order,
  user_id,
  display_name,
  username,
  display_handle,
  avatar_url,
  party_id,
  party_name,
  party_slug,
  party_logo_url,
  party_role,
  elected_count,
  candidated_count,
  updated_at
FROM parliament_current_members
WHERE guild_id = :guild_id
ORDER BY
  section_order ASC,
  slot_order ASC,
  user_id ASC;
```

Falls ihr nur die eigentlichen Kartenwerte für eine kompakte öffentliche Liste braucht:

```sql
SELECT
  slot_order,
  display_name,
  display_handle,
  avatar_url,
  party_name,
  party_logo_url,
  elected_count,
  candidated_count
FROM parliament_current_members
WHERE guild_id = :guild_id
  AND section_key = 'member'
ORDER BY slot_order ASC;
```

Wenn zusätzlich alle genehmigten Parteien mit Führungsrolle gebraucht werden, bleibt die bestehende Join-Query ebenfalls gültig:

```sql
SELECT
  p.id AS party_id,
  p.name AS party_name,
  p.slug,
  p.logo_url,
  m.user_id,
  m.role AS party_role,
  m.added_at
FROM parliament_parties p
JOIN parliament_party_members m
  ON m.party_id = p.id
WHERE p.guild_id = :guild_id
  AND p.status = 'approved'
ORDER BY
  p.name ASC,
  CASE WHEN m.role = 'leader' THEN 0 ELSE 1 END,
  m.user_id ASC;
```
