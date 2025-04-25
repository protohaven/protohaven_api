# syntax=docker/dockerfile:1

FROM node:20.18.1
WORKDIR /code

RUN corepack enable
RUN corepack install -g pnpm@9.14.4

COPY package.json package.json
COPY pnpm-lock.yaml pnpm-lock.yaml
RUN pnpm install

EXPOSE 5173
COPY . .
CMD ["pnpm", "run", "dev", "--host=0.0.0.0"]
