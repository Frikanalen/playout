FROM node:16-alpine AS deps

WORKDIR /home/node/app

COPY yarn.lock .
COPY package.json .

RUN yarn install --quiet --dev

FROM node:16-alpine AS builder

WORKDIR /home/node/app
COPY --from=deps /home/node/app/node_modules node_modules
COPY . .
#RUN yarn generate
RUN yarn build

FROM node:16-alpine AS runner

COPY . .
COPY --from=deps /home/node/app/node_modules node_modules
COPY --from=builder /home/node/app/build build
COPY --from=builder /home/node/app/src/generated src/generated
ENV PORT 80
ENV NODE_ENV production
EXPOSE 80

ENTRYPOINT ["yarn", "start"]
