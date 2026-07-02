from config.settings import settings

print("=" * 50)
print("CareerAI Configuration")
print("=" * 50)

print("App Name :", settings.APP_NAME)
print("Environment :", settings.APP_ENV)

print("Database Host :", settings.DB_HOST)
print("Database Port :", settings.DB_PORT)

print("Redis Host :", settings.REDIS_HOST)

print("RabbitMQ Host :", settings.RABBITMQ_HOST)

print("=" * 50)