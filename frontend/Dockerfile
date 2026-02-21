FROM node:20-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build Next.js
RUN npm run build

# Expose port
EXPOSE 3000

# Start server
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["npm", "start"]
