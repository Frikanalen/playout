FROM node:16-alpine as deps

WORKDIR /home/node/app

COPY yarn.lock .
COPY package.json .

RUN yarn install --quiet --dev

FROM node:16-alpine as builder

WORKDIR /home/node/app
COPY --from=deps /home/node/app/node_modules node_modules
COPY . .
RUN yarn build

FROM node:16-alpine as runner

COPY . .
COPY --from=deps /home/node/app/node_modules node_modules
COPY --from=builder /home/node/app/build build
RUN yarn generate
ENV PORT 80
ENV NODE_ENV production
EXPOSE 80

ENTRYPOINT ["yarn", "start"]
