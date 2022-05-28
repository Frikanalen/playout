"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.InterstitialGraphics = void 0;
const node_schedule_1 = __importDefault(require("node-schedule"));
const date_fns_1 = require("date-fns");
const config_1 = require("./config");
const _1 = require(".");
class InterstitialGraphics {
    startsAt;
    endsAt;
    jobs;
    compactTimestamp() {
        const { startsAt, endsAt } = this;
        return (0, date_fns_1.format)(startsAt, "HH:mm:ss.SSx - ") + (0, date_fns_1.format)(endsAt, "HH:mm:ss.SSx");
    }
    constructor(startsAt, endsAt) {
        this.startsAt = startsAt;
        this.endsAt = endsAt;
        this.jobs = [];
    }
    async load() {
        _1.log.info(`CG loading, URL: ${config_1.GRAPHICS_URL}`);
        await _1.connection.cgAdd(1, 100, 0, config_1.GRAPHICS_URL, false);
    }
    async play() {
        _1.log.info(`Playing CG`);
        await _1.connection.cgPlay(1, 100, 0);
    }
    async stop() {
        _1.log.info(`Stopping CG`);
        await _1.connection.cgStop(1, 100, 0);
    }
    async clear() {
        _1.log.info(`Clearing CG`);
        await _1.connection.cgClear(1, 100);
    }
    async arm() {
        const now = new Date();
        const { startsAt, endsAt, load, play, stop, clear } = this;
        const loadAt = (0, date_fns_1.sub)(startsAt, { seconds: 1 });
        const playAt = (0, date_fns_1.subMilliseconds)(startsAt, 500);
        const clearAt = (0, date_fns_1.add)(endsAt, { seconds: 2 });
        if (endsAt <= now) {
            _1.log.debug(`Not scheduling graphics {${endsAt} is in the past)`);
            return;
        }
        if (startsAt <= now) {
            _1.log.warn(`Graphics ${this.compactTimestamp()} should be running`);
            await load();
            setTimeout(async () => {
                await play();
            }, 1000);
            this.jobs = [
                node_schedule_1.default.scheduleJob(endsAt, stop),
                node_schedule_1.default.scheduleJob(clearAt, clear),
            ];
        }
        else {
            _1.log.debug(`Arming graphics for ${this.compactTimestamp()}`);
            this.jobs = [
                node_schedule_1.default.scheduleJob(loadAt, load),
                node_schedule_1.default.scheduleJob(playAt, play),
                node_schedule_1.default.scheduleJob(endsAt, stop),
                node_schedule_1.default.scheduleJob(clearAt, clear),
            ];
        }
    }
    async disarm() {
        for (const job of this.jobs) {
            job.cancel();
        }
    }
}
exports.InterstitialGraphics = InterstitialGraphics;
