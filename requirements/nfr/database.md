# NFR-D. 데이터베이스 (Database)

- **NFR-D01** 개발은 SQLite(`aiosqlite`, NullPool), 운영은 MySQL(`aiomysql`, pool_size=10, max_overflow=20)을 사용한다.
- **NFR-D02** DB 종류는 `DATABASE_URL`로 결정된다.
- **NFR-D03** 스키마는 시작 시 `create_all`로 생성되며, Alembic 마이그레이션도 사용 가능하다(`api/alembic/`).
