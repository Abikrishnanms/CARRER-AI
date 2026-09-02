import os

services = ['gateway', 'collector', 'cleaner', 'deduplicator', 'verifier', 'enrichment', 'embedder', 'notifier']

for s in services:
    os.makedirs(f'infra/docker/{s}', exist_ok=True)
    os.makedirs(f'services/{s}', exist_ok=True)
    with open(f'infra/docker/{s}/Dockerfile', 'w') as f:
        f.write(f'''FROM python:3.12-slim
WORKDIR /app
COPY ./services/{s} ./services/{s}
COPY ./shared ./shared
# Dummy entrypoint for now
CMD ["sleep", "infinity"]
''')

os.makedirs('frontend/admin/src', exist_ok=True)
with open('frontend/admin/Dockerfile', 'w') as f:
    f.write('''FROM node:18-alpine AS development
WORKDIR /app
CMD ["sleep", "infinity"]
''')

os.makedirs('frontend/jobboard/src', exist_ok=True)
with open('frontend/jobboard/Dockerfile', 'w') as f:
    f.write('''FROM node:18-alpine AS development
WORKDIR /app
CMD ["sleep", "infinity"]
''')

print('Dockerfiles created.')
