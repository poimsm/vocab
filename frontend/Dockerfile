# Etapa 1: Compilar la aplicación de Vue
FROM node:20-alpine AS build-stage
WORKDIR /app

ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE

COPY ./frontend/package*.json ./
RUN npm install

COPY ./frontend/ ./
RUN npm run build

# Etapa 2: Servir con Nginx
FROM nginx:alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]