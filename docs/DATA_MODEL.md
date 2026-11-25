# QR — Финальная логическая и физическая модель данных
Версия: 1.0
Статус: утверждена для реализации; физическая схема PostgreSQL описана в migrations/postgresql
Дата утверждения ключевых решений: 2026-11-25

## 1. Зафиксированные продуктовые решения

1. `part_code` уникален в пределах организации: `UNIQUE (organization_id, part_code)`. Между организациями одинаковые коды допустимы.
2. Пользователь может состоять в нескольких организациях. Роли назначаются членству, а не глобально пользователю.
3. Сборки и спецификации входят в базовую модель. Сборка — специальный вид детали; её состав хранится как BOM (bill of materials) с количеством, единицей измерения, позицией и ссылкой на конкретную ревизию компонента при необходимости.
4. История файлов и версий не ограничивается прикладным лимитом. Версии не перезаписываются. Физическое удаление допускается только по отдельной административной процедуре/политике хранения, а не как обычное редактирование.
5. Windows desktop — первая платформа; сервер PostgreSQL на VPS; локальная БД SQLite/SQLCipher; локальные файлы шифруются аутентифицированным шифрованием.
6. UUID — внутренний неизменяемый идентификатор. Код детали — отдельный человекочитаемый атрибут.

## 2. Общие правила

- Время — UTC, тип PostgreSQL `timestamptz`; SQLite хранит ISO-8601 UTC.
- UUID генерируется приложением (UUIDv7 предпочтителен для новых записей; UUIDv4 допустим).
- Все сущности организации имеют `organization_id`.
- Для tenant-owned связей используются составные FK, включающие `organization_id`, чтобы БД не позволяла связать сущности разных организаций.
- Опубликованные ревизии детали и версии документа неизменяемы.
- Удаления синхронизируемых объектов сначала создают tombstone (`deleted_at`), физическое удаление не используется в обычном API.
- JSONB используется для расширяемых атрибутов/snapshot, но не вместо нормализованных отношений, прав или BOM.
- Файлы хранятся в приватном object storage или зашифрованном локальном vault. БД содержит только метаданные и непрозрачный storage key.
- `organization_id` никогда не принимается как источник полномочий из клиентского payload: tenant определяется сервером из проверенного членства.

## 3. Identity, tenants и access control

### users
`id, email_normalized, display_name, password_hash nullable, auth_provider, auth_subject, status, mfa_enabled, created_at, updated_at, last_login_at`.
Уникальность email — по нормализованному адресу. Для внешней аутентификации уникальна пара (auth_provider, auth_subject).

### organizations
`id, name, slug, status, created_at, updated_at`. Slug глобально уникален.

### memberships
`id, organization_id, user_id, status, joined_at, created_at, updated_at`.
Уникально `(organization_id,user_id)`. У пользователя может быть много membership.

### permissions / roles / role_permissions / membership_roles
Permissions — системный каталог ключей. Роли принадлежат конкретной организации. Одно членство может иметь несколько ролей. Уникальность роли — `(organization_id,key)`. Составной FK membership_roles гарантирует, что роль и членство относятся к одной организации.
Platform Owner не является обычной ролью организации; его доступ — отдельная системная идентичность и MFA.

## 4. Инженерный каталог

### parts
`id, organization_id, part_code, title, description, kind, status, attributes_json, current_revision_id, created_by, updated_by, created_at, updated_at, deleted_at`.
- `kind`: `part | assembly`.
- `status`: `draft | active | archived`.
- `UNIQUE(organization_id, part_code)`, без глобальной уникальности.
- `attributes_json` — только расширяемые параметры; основные поисковые поля остаются отдельными колонками.
- UUID детали постоянен; смена кода не меняет UUID и QR locator.

### part_revisions
Неизменяемые snapshots: `id, organization_id, part_id, revision_number, snapshot_json, change_summary, created_by, created_at`. Уникально `(part_id,revision_number)`. Смена текущей ревизии выполняется одной транзакцией вместе с созданием ревизии.

### categories / part_categories / tags / part_tags
Дерево категорий внутри организации; теги нормализованы в рамках организации. Composite FK не допускают межорганизационные связи.

### assemblies и BOM
Отдельная таблица assemblies не нужна: сборка — `parts.kind='assembly'`. Таблица `bom_items` содержит:
- `id, organization_id, assembly_part_id, component_part_id`;
- `component_revision_id nullable` — если состав фиксирует конкретную ревизию;
- `quantity numeric(20,6) > 0`, `unit_code`, `position_no`, `find_number`, `notes`;
- `created_at, updated_at, deleted_at`.
Одна сборка может иметь много строк состава. Компонентом может быть деталь или вложенная сборка. Составные FK обеспечивают один tenant. Циклы BOM (сборка включает саму себя напрямую/через вложенные сборки) проверяются доменным сервисом транзакционно; перед публикацией спецификации обязателен graph-cycle check. Порядок строк задаётся `position_no`, не порядком вставки.

### part_relations
Для дополнительных отношений, не являющихся BOM: замена, аналог, сопряжённая деталь и т.п. BOM не дублируется в этой таблице.

## 5. Документы и файлы

### documents
Логический файл: `id, organization_id, original_filename, detected_mime_type, extension, created_by, created_at, deleted_at`.

### document_versions
Неизменяемые версии бинарного содержимого: `id, organization_id, document_id, version_number, storage_key, checksum_sha256, size_bytes, encryption_metadata, scan_status, created_by, created_at`. Уникально `(document_id,version_number)`. Каждая новая загрузка создаёт новую версию; старые версии сохраняются. Нет прикладного ограничения числа версий.

### part_documents
Связывает деталь/сборку с версией документа и ролью (`drawing, model_3d, image, specification, passport, other`). Спецификация может быть как отдельным файлом, так и структурированным BOM; эти варианты не исключают друг друга.

## 6. QR

`qr_routes` хранит `id, organization_id, part_id, route_token_hash, status, created_by, created_at, revoked_at`. В QR помещается непрозрачный случайный locator, но не право доступа. Сервер проверяет аутентификацию, членство и разрешение на объект. Хранится только hash locator-токена. Для перевыпуска создаётся/активируется новый маршрут, старый отзывается.

## 7. Лицензирование и устройства

`licenses, license_entitlements, owner_feature_policies, device_installations, license_leases`.
Lease — подписанный сервером payload с версией схемы, tenant/license/installation, issued/not-before/expires/offline-until, features, policy version и key id. Приватный ключ подписи не хранится в БД клиента и не передаётся ему. После offline_until клиент блокирует рабочее пространство, но сохраняет зашифрованные данные и outbox. Сервер перепроверяет права при каждом API-вызове.

## 8. Синхронизация

- `sync_operations`: idempotent operation_id, tenant, installation, entity type/id, base revision, operation type, JSON payload, state, timestamps, result.
- `sync_cursors`: последний применённый серверный cursor для установки/организации.
- `sync_conflicts`: base/server revision, клиентский payload, статус и разрешение.
- Клиент атомарно записывает доменное изменение и outbox в одной локальной транзакции.
- Сервер дедуплицирует по operation_id. Pull cursor подтверждается только после применения пакета локально.
- Ошибки/конфликты не приводят к молчаливому затиранию данных.

## 9. Audit

Append-oriented `audit_events`: actor, tenant, action, target, outcome, correlation id, metadata, timestamp. Обычные роли не получают UPDATE/DELETE. Для защиты от администратора БД нужен внешний append-only export/подпись или WORM storage — один SQL constraint не обеспечивает абсолютную неизменяемость.

## 10. Tenant isolation и PostgreSQL RLS

Все tenant таблицы используют `organization_id`. В запросной транзакции API выставляет `app.current_organization_id` из проверенного контекста. RLS включается как дополнительная защита. Роль приложения не должна быть superuser, owner таблиц или иметь BYPASSRLS. Для миграций используется отдельная роль. Составные FK остаются обязательными даже при RLS.

## 11. Локальная SQLite-проекция

SQLite — локальный cache + offline write model, а не authority для лицензии/прав на сервере. Файл БД шифруется SQLCipher. Документы шифруются AES-256-GCM (или утверждённым AEAD) с уникальными nonce; ключи защищаются DPAPI. Локальная схема повторяет необходимые доменные поля, но может включать только выбранные организации/данные. Все локальные таблицы имеют `organization_id`; outbox/inbox/cursors — отдельные таблицы. Перед миграцией создаётся проверенная резервная копия; migration version хранится в `PRAGMA user_version` или таблице schema_migrations.

## 12. Индексы

Обязательные индексы включены в PostgreSQL migration: уникальность email/slug, membership, tenant part_code, каталог по статусу/обновлению, revisions, BOM по assembly/component, document checksum, QR hash, sync queue, cursor, audit chronology. Дополнительные индексы добавляются после EXPLAIN ANALYZE.

## 13. Политика хранения

История ревизий деталей и файлов не ограничивается числом версий. Удаление из интерфейса — tombstone. Удаление бинарных объектов и персональных данных — отдельная операция с проверкой legal/backup/retention obligations, аудитом и подтверждением. Unlimited означает отсутствие искусственного лимита версий, но не бесконечную ёмкость VPS: мониторинг диска, резервирование и план расширения обязательны.

## 14. Статус реализации

Эта модель и SQL migrations задают контракт для реализации. Они не означают, что сервер, клиент, шифрование, RLS или синхронизация уже реализованы/проверены в работающем приложении. До production нужны integration tests, tenant-isolation tests, security review, migration rehearsal и restore test.
