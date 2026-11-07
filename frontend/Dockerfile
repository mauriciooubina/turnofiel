FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=https://localhost
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM caddy:2.10-alpine
COPY --from=build /app/dist /srv
