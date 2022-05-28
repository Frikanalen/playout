"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.connection = exports.log = void 0;
const casparcg_connection_1 = require("casparcg-connection");
const client_1 = require("./client");
const config_1 = require("./config");
const tslog_1 = require("tslog");
const InterstitialGraphics_1 = require("./InterstitialGraphics");
const ScheduledVideo_1 = require("./ScheduledVideo");
const date_fns_1 = require("date-fns");
exports.log = new tslog_1.Logger();
client_1.OpenAPI.BASE = config_1.FK_API;
exports.connection = new casparcg_connection_1.CasparCG(config_1.CASPAR_HOST);
const getSchedule = async () => {
    const schedule = await client_1.SchedulingService.getSchedule((0, date_fns_1.startOfToday)().toISOString(), (0, date_fns_1.endOfToday)().toISOString());
    if (!schedule.length)
        throw new Error(`Schedule loaded, contained 0 items!`);
    exports.log.info(`Schedule loaded ${schedule.length} items.`);
    return schedule;
};
const get = async () => {
    const scheduledEntries = [];
    const addToSchedule = async (entry) => {
        await entry.arm();
        scheduledEntries.push(entry);
    };
    try {
        await exports.connection.mixerClear(1);
        await exports.connection.clear(1);
        const schedule = await getSchedule();
        let previousEntryEnded;
        for (const entry of schedule) {
            const thisEntryStarts = new Date(entry.startsAt);
            await addToSchedule(new ScheduledVideo_1.ScheduledVideo(entry));
            if (previousEntryEnded !== undefined) {
                await addToSchedule(new InterstitialGraphics_1.InterstitialGraphics(previousEntryEnded, thisEntryStarts));
            }
            previousEntryEnded = new Date(entry.endsAt);
        }
    }
    catch (e) {
        exports.log.error("error", e);
    }
};
(async () => {
    try {
        exports.log.info(`Starting playout at ${new Date().toLocaleString()}`);
        var text = await get();
    }
    catch (e) {
        console.log(e);
        // Deal with the fact the chain failed
    }
})();
