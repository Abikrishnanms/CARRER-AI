# ── Development Stage ──────────────────────────────────────────────────────────
# Serves vanilla HTML/CSS/JS files from the current directory using http-server
FROM node:20-alpine AS development

WORKDIR /app

# Install a tiny zero-config static file server globally
RUN npm install -g http-server

# Copy static assets (index.html, app.js, style.css, src/)
COPY . .

EXPOSE 3000

# http-server: serve ./ on port 3000, allow CORS, auto-gzip, fall back to index.html
CMD ["http-server", ".", "-p", "3000", "-a", "0.0.0.0", "--cors", "-g", "-P", "http://localhost:3000?"]

# ── Production Stage ───────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production

RUN rm -rf /usr/share/nginx/html/*

# Copy static assets directly (no build step for vanilla HTML)
COPY . /usr/share/nginx/html

RUN printf 'server {\n\
    listen 3000;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    gzip on;\n\
    gzip_types text/plain application/json application/javascript text/css;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    location ~* \.(?:ico|css|js|gif|jpe?g|png|woff2?)$ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]

