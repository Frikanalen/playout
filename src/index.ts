import { OpenAPI } from "./generated/index.js";
import { FK_API, LAYERS } from "./config.js";
import process from "node:process";
import { log } from "./log.js";
import { ScheduleLoader } from "./scheduling/ScheduleLoader.js";
import { timeline } from "./scheduling/Timeline.js";
import { startWebsocketServer } from "./api/server.js";
import { getSchedule } from "./getSchedule.js";
import { caspar } from "./caspar/connection.js";
OpenAPI.BASE = FK_API!;

process
  .on("unhandledRejection", (reason, p) => {
    log.error(reason, "Unhandled Rejection at Promise", p);
  })
  .on("uncaughtException", (err) => {
    log.error(err, "Uncaught Exception thrown");
    process.exit(1);
  });

const initCaspar = async () => {
  log.info(`Connecting to CasparCG host [${caspar.host}]...`);
  await caspar.connect();

  log.info(`Clearing all layers...`);

  await caspar.mixerClear({ channel: 1, layer: LAYERS.graphics });
  await caspar.mixerClear({ channel: 1, layer: LAYERS.video });
  await caspar.mixerClear({ channel: 1, layer: LAYERS.logo });

  await caspar.clear({ channel: 1 });
};

const runPlayout = async () => {
  await initCaspar();

  const schedule = new ScheduleLoader();

  // noinspection InfiniteLoopJS
  while (true) {
    await schedule.load(await getSchedule());
    await timeline.run();
  }
};

(async () => {
  try {
    log.info(`Starting playout at ${new Date().toLocaleString()}`);
    startWebsocketServer(8080);
    await runPlayout();
  } catch (e) {
    log.error(e);
  }
})();
