import { OpenAPI } from "./generated/index.js";
import { FK_API, LAYERS } from "./config.js";
import process from "node:process";
import { log } from "./log.js";
import { ScheduleLoader } from "./scheduling/ScheduleLoader.js";
import { connection } from "./connection.js";
import { endOfDay, startOfDay } from "date-fns";
import { timeline } from "./scheduling/Timeline.js";
import { makeTestSchedule } from "./scheduling/testUtils.js";
import { startWebsocketServer } from "./api/server.js";

OpenAPI.BASE = FK_API;

process
  .on("unhandledRejection", (reason, p) => {
    log.error(reason, "Unhandled Rejection at Promise", p);
  })
  .on("uncaughtException", (err) => {
    log.error(err, "Uncaught Exception thrown");
    process.exit(1);
  });

const initCaspar = async () => {
  log.info(`Connecting to CasparCG host "${connection.host}"...`);
  await connection.connect();

  log.info(`Clearing all layers...`);
  // get layers with contents
  const infoRequest = await connection.info({ channel: 1 });
  const info = await infoRequest.request;
  log.info(JSON.stringify(info?.data));

  await connection.mixerClear({ channel: 1, layer: LAYERS.graphics });
  await connection.mixerClear({ channel: 1, layer: LAYERS.video });
  await connection.mixerClear({ channel: 1, layer: LAYERS.logo });

  await connection.clear({ channel: 1 });
};

const runPlayout = async () => {
  await initCaspar();

  const schedule = new ScheduleLoader();

  while (true) {
    const now = new Date();
    /*const scheduleEntries = await SchedulingService.getSchedule(
      startOfDay(now).toISOString(),
      endOfDay(now).toISOString()
    );*/
    const scheduleEntries = makeTestSchedule(
      startOfDay(now).toISOString(),
      endOfDay(now).toISOString(),
    );
    await schedule.load(scheduleEntries);
    await timeline.run();
  }
};

(async () => {
  try {
    log.info(`Starting playout at ${new Date().toLocaleString()}`);
    await startWebsocketServer(8080);
    await runPlayout();
  } catch (e) {
    log.error(e);
  }
})();
