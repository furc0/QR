# QR — Модель данных
Версия: 0.1  
Статус: логическая модель для review перед созданием миграций  
Связанные документы: TECHNICAL_SPECIFICATION.md, ARCHITECTURE.md

## 1. Принципы модели

1. Каждая инженерная сущность имеет неизменяемый UUID.
2. Все данные организации изолируются через organization_id.
3. Лицензии и глобальные политики принадлежат центральному контуру и не редактируются администраторами организаций.
4. Инженерные ревизии и версии документов неизменяемы после публикации; исправление создаёт новую версию.
5. Удаление синхронизируемых сущностей использует tombstone, а не физическое удаление сразу.
6. Временные метки хранятся в UTC.
7. Схема должна быть реализуема на PostgreSQL и иметь совместимую проекцию на SQLite.
8. Секреты, пароли, открытые ключи подписи и содержимое файлов не хранятся в обычных полях карточек.

## 2. Идентификаторы и соглашения

- Primary key: UUID.
- Внешние ключи: UUID с явными ограничениями.
- Код детали: отдельное поле part_code; не используется как PK.
- Денежные/измерительные величины не хранятся в float без единиц и точности.
- Размеры хранятся с указанием единиц измерения и валидируемой точности.
- JSON-поля разрешены для расширяемых инженерных атрибутов и snapshot, но критичные связи и права остаются нормализованными.

## 3. Основные сущности

### 3.1 Identity и организация

**users**
- id
- login/email (уникальность и нормализация уточняются)
- password_hash или внешний identity subject
- status
- mfa_state
- created_at, updated_at, last_login_at

**organizations**
- id
- name
- slug
- status
- created_at, updated_at

**memberships**
- id
- organization_id
- user_id
- status
- created_at
- UNIQUE(organization_id, user_id)

**roles**
- id
- organization_id nullable для системных шаблонов
- key
- name
- is_system
- UNIQUE(organization_id, key)

**permissions**
- id
- key
- description
- UNIQUE(key)

**role_permissions**
- role_id
- permission_id
- PRIMARY KEY(role_id, permission_id)

**membership_roles**
- membership_id
- role_id
- PRIMARY KEY(membership_id, role_id)

Platform Owner не назначается через обычную membership role. Его полномочия задаются отдельной защищённой системной идентичностью/allowlist и MFA.

### 3.2 Каталог

**parts**
- id
- organization_id
- part_code
- title
- description
- status: draft | active | archived
- current_revision_id nullable
- created_by
- created_at, updated_at
- deleted_at nullable (tombstone)

Ограничения:
- UNIQUE(organization_id, part_code).
- FK на organization и пользователя.
- Все операции по parts фильтруются по organization_id из доверенного контекста.

**part_revisions**
- id
- organization_id
- part_id
- revision_number
- snapshot_json
- change_summary
- created_by
- created_at
- UNIQUE(part_id, revision_number)

Ревизия — immutable snapshot. Изменение карточки создаёт новую ревизию и меняет current_revision_id в одной транзакции.

**categories**
- id
- organization_id
- parent_id nullable
- name
- code nullable
- sort_order
- status

**part_categories**
- part_id
- category_id
- PRIMARY KEY(part_id, category_id)

**tags**
- id
- organization_id
- name
- normalized_name

**part_tags**
- part_id
- tag_id
- PRIMARY KEY(part_id, tag_id)

**part_relations**
- id
- organization_id
- source_part_id
- target_part_id
- relation_type (например, assembly_component, replacement, related)
- quantity nullable
- unit nullable

Ограничить циклические/некорректные отношения правилами доменного слоя; для сборок предусмотреть проверку циклов.

### 3.3 Документы и файлы

**documents**
- id
- organization_id
- original_filename
- detected_mime_type
- extension
- size_bytes
- checksum_sha256
- storage_key
- scan_status
- created_by
- created_at
- deleted_at nullable

**document_versions**
- id
- organization_id
- document_id
- version_number
- checksum_sha256
- storage_key
- size_bytes
- created_by
- created_at
- UNIQUE(document_id, version_number)

**part_documents**
- part_id
- document_version_id
- document_role (drawing, model_3d, image, specification, other)
- display_order
- PRIMARY KEY(part_id, document_version_id, document_role)

Файловое содержимое хранится в приватном object storage или локальном зашифрованном хранилище. В БД хранятся метаданные и ключ хранения, но не публичный постоянный URL.

### 3.4 QR-маршруты

**qr_routes**
- id
- organization_id
- part_id
- route_token_hash
- status
- created_by
- created_at
- revoked_at nullable

В QR не помещается постоянный секрет авторизации. Если маршрут содержит случайный идентификатор, сервер всё равно требует входа и проверки доступа. Хранить hash токена, если токен используется как bearer-like locator. Не использовать последовательный ID как единственную защиту.

### 3.5 Лицензии и функции

**licenses**
- id
- organization_id
- status
- valid_from
- valid_until
- license_reference
- created_at
- updated_at

**license_entitlements**
- id
- license_id
- feature_key
- enabled
- limits_json nullable
- UNIQUE(license_id, feature_key)

**owner_feature_policies**
- id
- feature_key
- enabled
- policy_json
- policy_version
- updated_by_owner
- updated_at

Глобальная политика хранится в центральном контуре. Клиент и Organization Admin не имеют API-пути на изменение этой таблицы.

**license_leases**
- id
- license_id
- organization_id
- installation_id nullable
- issued_at
- not_before
- expires_at
- offline_until
- payload_version
- signing_key_id
- signed_payload
- signature
- status
- revoked_at nullable

Подписанный payload должен быть воспроизводимо канонизирован. Закрытый ключ подписи не хранится в этой таблице и не передаётся клиенту.

**device_installations**
- id
- organization_id
- user_id nullable
- public_key nullable
- device_label
- platform
- status
- first_seen_at
- last_seen_at
- revoked_at nullable

### 3.6 Синхронизация

**sync_operations**
- operation_id (UUID, уникальный)
- organization_id
- installation_id
- entity_type
- entity_id
- base_revision nullable
- operation_type
- payload
- status
- received_at
- processed_at nullable
- result_json nullable

Уникальность operation_id предотвращает повторное применение одной операции.

**sync_cursors**
- id
- organization_id
- installation_id
- cursor_value
- updated_at
- UNIQUE(organization_id, installation_id)

**sync_conflicts**
- id
- organization_id
- installation_id
- entity_type
- entity_id
- base_revision
- server_revision
- client_payload
- status
- resolution
- created_at
- resolved_at nullable

### 3.7 Аудит

**audit_events**
- id
- organization_id nullable для глобальных событий
- actor_user_id nullable для системных действий
- actor_type
- action
- target_type
- target_id nullable
- outcome
- correlation_id
- metadata_json
- created_at

Audit events append-only на уровне приложения и ограничений БД. Обычные администраторы не имеют права UPDATE/DELETE. Для повышенной защиты возможна периодическая подпись/хеш-цепочка событий и экспорт в отдельное хранилище.

## 4. Отношения сущностей

- Organization 1—N Membership.
- User 1—N Membership.
- Organization 1—N Part.
- Part 1—N PartRevision.
- Part N—N Category через PartCategory.
- Part N—N Tag через PartTag.
- Part N—N DocumentVersion через PartDocument.
- Organization 1—N License.
- License 1—N Entitlement.
- License 1—N LicenseLease.
- Organization 1—N DeviceInstallation.
- DeviceInstallation 1—N SyncOperation и SyncCursor.
- Organization 1—N AuditEvent (глобальные события владельца могут иметь organization_id NULL).

## 5. Tenant isolation и ограничения

1. Каждый tenant-owned запрос получает organization_id из серверной сессии/membership context.
2. Запрещено принимать organization_id из тела запроса как источник полномочий.
3. Все репозитории данных требуют tenant context параметром.
4. Для критичных таблиц использовать составные уникальные ключи/FK с organization_id там, где это помогает предотвратить cross-tenant ссылки.
5. Рассмотреть PostgreSQL Row-Level Security как дополнительный барьер, но не заменять им проверки в сервисах.
6. Для SQLite offline данные привязаны к локальному профилю организации и зашифрованы; при синхронизации сервер повторно проверяет tenant membership и разрешения.
7. Набор интеграционных тестов обязан пытаться подменить part_id, document_id, route_id и organization_id.

## 6. Разрешения и матрица функций

Базовые permission keys:

| Permission | Platform Owner | Org Admin | Designer | Engineer | Viewer |
|---|---:|---:|---:|---:|---:|
| catalog.read | Да | Да | Да | Да | Да |
| catalog.create | Да | Да | Да | Нет | Нет |
| catalog.update | Да | Да | Да | По назначению | Нет |
| catalog.archive | Да | Да | По назначению | Нет | Нет |
| documents.read | Да | Да | Да | Да | Да |
| documents.upload | Да | Да | Да | По назначению | Нет |
| documents.export | Да | Да | По назначению | По назначению | Нет |
| viewer3d.view | Да | Да | Да | Да | По лицензии |
| users.manage | Да | Да | Нет | Нет | Нет |
| organization.settings | Да | Да | Нет | Нет | Нет |
| global.license.manage | Да | Нет | Нет | Нет | Нет |
| global.feature_policy.manage | Да | Нет | Нет | Нет | Нет |

Таблица задаёт шаблон, а не безусловную выдачу. Глобальная политика и entitlement лицензии могут запретить функцию. Org Admin не получает глобальные права Platform Owner.

## 7. Индексы и производительность

Начальные индексы:
- parts(organization_id, part_code) UNIQUE;
- parts(organization_id, status, updated_at);
- part_revisions(part_id, revision_number) UNIQUE;
- documents(organization_id, checksum_sha256);
- qr_routes(organization_id, route_token_hash) UNIQUE;
- memberships(user_id, organization_id);
- sync_operations(installation_id, status, received_at);
- audit_events(organization_id, created_at);
- license_leases(license_id, offline_until, status).

Индексы уточняются по реальным запросам и EXPLAIN ANALYZE. Не добавлять индексы на все поля без измерений.

## 8. Локальная SQLite-проекция

SQLite хранит только данные, необходимые текущей установке и разрешённые для локального кэширования:
- выбранные организации и локальный контекст пользователя;
- карточки и ревизии, доступные установке;
- метаданные документов и зашифрованные файлы;
- outbox/inbox;
- sync cursor;
- подписанный lease и его состояние;
- локальные настройки темы.

Локальная схема должна иметь migration version. Миграции выполняются транзакционно, с резервной копией перед потенциально разрушительными изменениями. Нельзя полагаться на то, что SQLite и PostgreSQL полностью одинаковы по типам и поведению; различия изолируются в repository/adapters.

## 9. Решения, которые нужно утвердить перед миграциями

1. Уникальность part_code: внутри организации или глобально.
2. Нужны ли несколько организаций одному пользователю в первой версии.
3. Какие поля карточки обязательны и какие пользователь может настраивать.
4. Нужны ли сборки и спецификации в MVP или только отдельные детали.
5. Требуется ли хранить оригинальные файлы без ограничения срока.
6. Допустимые размеры файлов и модели.
7. Политика хранения audit events и срок хранения удалённых данных.
8. Как устроить восстановление локального ключа при смене Windows-профиля/ПК.

После утверждения этих решений модель превращается в Prisma schema/SQL migrations и SQLite migrations. До этого не создавать необратимые production-миграции.
