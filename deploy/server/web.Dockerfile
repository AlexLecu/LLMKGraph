# Vue UI + same-origin reverse proxy for the API, the chatbot and the evaluation app.
# Built by deploy/server/docker-compose.yml (context: frontend/, extra context "server").
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Every backend is reached through this container, so the UI uses relative URLs
ENV VITE_API_URL=/ \
    VITE_CHAT_URL=/chatbot/ \
    VITE_EVAL_URL=/streamlit/?embed=true&embed_options=show_toolbar \
    VITE_DEFAULT_REPO=amd_abstracts
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=server nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
