FROM node:20-alpine

WORKDIR /app

# Install dependencies first (layer-cached until package.json changes)
COPY package*.json ./
RUN npm ci --production

# Copy app code (not data — that comes from a volume at runtime)
COPY server.js ./
COPY public ./public
COPY scripts ./scripts

EXPOSE 3000

CMD ["node", "server.js"]
