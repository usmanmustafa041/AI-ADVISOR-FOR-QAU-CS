# Database Migrations

This directory contains database schema migration scripts for the QAU CS Academic Advisor system.

## Migration Files

### upgrade_chatbot_schema.sql

**Purpose**: Chatbot Intelligence Upgrade - Add tables for faculty information, research areas, news, events, web scraper tracking, and enhanced feedback

**Requirements**: 27, 28, 22 (from chatbot-intelligence-upgrade spec)

**Dependencies**: 
- Base `schema.sql` must be applied first
- Requires `pgvector` extension for vector embeddings
- Requires `source_records` and `chat_messages` tables from base schema

**Tables Added**:
1. `faculty_members` - Faculty profile information
2. `faculty_research_interests` - Faculty research interests (free text)
3. `research_areas` - Structured research areas/domains
4. `faculty_research_areas` - Many-to-many junction table
5. `news_articles` - Department news and announcements
6. `events` - Department events with scheduling info
7. `scraper_runs` - Web scraper execution audit log
8. `chat_feedback` - User feedback on chatbot responses

**Key Features**:
- Full-text search indexes (GIN) on faculty names, research interests, news content
- Temporal indexes (B-tree) for efficient date-based queries
- Foreign key constraints linking to `source_records` for traceability
- Backward compatible with existing schema
- Idempotent (safe to run multiple times with `IF NOT EXISTS`)

## How to Apply Migrations

### Development/Local Environment

```bash
# Apply migration to local database
psql -h localhost -U youruser -d qau_cs_advisor -f database/migrations/upgrade_chatbot_schema.sql
```

### Docker Environment

```bash
# Copy migration to database container and apply
docker cp database/migrations/upgrade_chatbot_schema.sql qau-cs-advisor-db:/tmp/
docker exec -it qau-cs-advisor-db psql -U postgres -d qau_cs_advisor -f /tmp/upgrade_chatbot_schema.sql
```

### Verification

After applying the migration, verify all tables were created:

```sql
-- Check new tables
SELECT table_name, 
       (SELECT count(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_name IN (
    'faculty_members',
    'faculty_research_interests', 
    'research_areas',
    'faculty_research_areas',
    'news_articles',
    'events',
    'scraper_runs',
    'chat_feedback'
)
ORDER BY table_name;

-- Check indexes
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN (
    'faculty_members',
    'faculty_research_interests',
    'research_areas', 
    'faculty_research_areas',
    'news_articles',
    'events',
    'scraper_runs',
    'chat_feedback'
)
ORDER BY tablename, indexname;
```

## Migration Best Practices

1. **Always backup** your database before applying migrations
2. **Test migrations** in a development environment first
3. **Review verification queries** at the end of each migration script
4. **Check for errors** in the output after applying migrations
5. **Document schema changes** in this README when adding new migrations

## Rollback Considerations

This migration does not include a rollback script because:
- All tables use `IF NOT EXISTS` making the migration idempotent
- New tables do not modify existing tables or data
- Dropping the new tables would require careful consideration of foreign key relationships

To manually rollback (if needed):

```sql
-- WARNING: This will delete all data in the new tables
BEGIN;

DROP TABLE IF EXISTS chat_feedback CASCADE;
DROP TABLE IF EXISTS scraper_runs CASCADE;
DROP TABLE IF EXISTS faculty_research_areas CASCADE;
DROP TABLE IF EXISTS faculty_research_interests CASCADE;
DROP TABLE IF EXISTS faculty_members CASCADE;
DROP TABLE IF EXISTS research_areas CASCADE;
DROP TABLE IF EXISTS news_articles CASCADE;
DROP TABLE IF EXISTS events CASCADE;

COMMIT;
```

## Future Migrations

When adding new migrations:

1. Create a new `.sql` file with a descriptive name and date
2. Use transaction blocks (`BEGIN`/`COMMIT`)
3. Include verification queries at the end
4. Document in this README
5. Test thoroughly before applying to production
