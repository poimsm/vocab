# Etapa 1: Compilar la aplicación de Vue
FROM node:20-alpine AS build-stage
WORKDIR /app

# 👇 CORRECCIÓN: Apuntamos a la carpeta frontend/ que está en la raíz del contexto
COPY ./frontend/package*.json ./
RUN npm install

# 👇 CORRECCIÓN: Copiamos todo el contenido de la carpeta frontend/ al contenedor
COPY ./frontend/ ./
RUN npm run build

# Etapa 2: Servir con Nginx
FROM nginx:alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]