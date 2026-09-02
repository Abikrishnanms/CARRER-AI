FROM python:3.12-alpine AS development
WORKDIR /app
COPY . .
EXPOSE 3001
CMD ["python3", "-m", "http.server", "3001"]

FROM nginx:1.27-alpine AS production
RUN rm -rf /usr/share/nginx/html/*
COPY . /usr/share/nginx/html
EXPOSE 3001
CMD ["python3", "-m", "http.server", "3001"]
