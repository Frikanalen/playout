FROM node:18-alpine AS deps

WORKDIR /home/node/app

COPY yarn.lock .
COPY package.json .

RUN yarn install --quiet --dev

FROM node:18-alpine AS builder

WORKDIR /home/node/app
COPY --from=deps /home/node/app/node_modules node_modules
COPY . .
RUN yarn generate
RUN yarn build

FROM node:18-alpine AS runner
WORKDIR /home/node/app

COPY . .
COPY --from=deps /home/node/app/node_modules node_modules
COPY --from=builder /home/node/app/build build
ENV PORT 80
ENV NODE_ENV production
EXPOSE 80

ENTRYPOINT ["yarn", "start"]
