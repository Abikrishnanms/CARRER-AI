FROM python:3.12-alpine AS development
WORKDIR /app
COPY . .
EXPOSE 3000
CMD ["python3", "-m", "http.server", "3000"]

FROM nginx:1.27-alpine AS production
RUN rm -rf /usr/share/nginx/html/*
COPY . /usr/share/nginx/html
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
