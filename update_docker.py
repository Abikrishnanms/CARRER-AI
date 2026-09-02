import re

with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace volumes
content = content.replace('  postgres_data:\n', '  mongodb_data:\n')

# Replace postgres service with mongodb
postgres_service = """  # PostgreSQL — Primary database
  postgres:
    image: postgres:16-alpine
    container_name: jip-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-jobplatform}
      POSTGRES_USER: ${POSTGRES_USER:-jobplatform}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-jobplatform_dev_password}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - platform
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-jobplatform}"]
      interval: 10s
      timeout: 5s
      retries: 5"""

mongodb_service = """  # MongoDB — Primary database for unstructured data
  mongodb:
    image: mongo:7.0
    container_name: jip-mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER:-admin}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD:-admin123}
      MONGO_INITDB_DATABASE: ${MONGO_DB:-jobplatform}
    volumes:
      - mongodb_data:/data/db
    ports:
      - "27017:27017"
    networks:
      - platform
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5"""

content = content.replace(postgres_service, mongodb_service)

# Replace DATABASE_URL in services
db_url_pattern = r'- DATABASE_URL=postgresql\+asyncpg://\$\{POSTGRES_USER:-jobplatform\}:\$\{POSTGRES_PASSWORD:-jobplatform_dev_password\}@postgres:5432/\$\{POSTGRES_DB:-jobplatform\}'
mongo_uri_replacement = '- MONGO_URI=mongodb://${MONGO_USER:-admin}:${MONGO_PASSWORD:-admin123}@mongodb:27017/${MONGO_DB:-jobplatform}?authSource=admin'
content = re.sub(db_url_pattern, mongo_uri_replacement, content)

# Update depends_on for gateway, cleaner, verifier
content = content.replace('''    depends_on:
      postgres:
        condition: service_healthy''', '''    depends_on:
      mongodb:
        condition: service_healthy''')

# Update mlflow backend store and depends_on
content = content.replace('''      --backend-store-uri postgresql://${POSTGRES_USER:-jobplatform}:${POSTGRES_PASSWORD:-jobplatform_dev_password}@postgres:5432/mlflow''', '''      --backend-store-uri sqlite:////mlflow/mlflow.db''')

content = content.replace('''    depends_on:
      postgres:
        condition: service_healthy
      minio:''', '''    depends_on:
      minio:''')

# Add mlflow_db volume to mlflow
mlflow_block = '''    environment:
      - AWS_ACCESS_KEY_ID=${MINIO_ACCESS_KEY:-minioadmin}'''
mlflow_replacement = '''    volumes:
      - ./mlflow_data:/mlflow
    environment:
      - AWS_ACCESS_KEY_ID=${MINIO_ACCESS_KEY:-minioadmin}'''
content = content.replace(mlflow_block, mlflow_replacement)

with open('docker-compose.yml', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done replacing in docker-compose.yml')
