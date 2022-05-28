"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ScheduledVideo = void 0;
const date_fns_1 = require("date-fns");
const _1 = require(".");
const config_1 = require("./config");
const node_schedule_1 = __importDefault(require("node-schedule"));
class ScheduledVideo {
    entry;
    jobs;
    startsAt;
    endsAt;
    videoTitle;
    constructor(entry) {
        this.entry = entry;
        this.startsAt = new Date(entry.startsAt);
        this.endsAt = new Date(entry.endsAt);
        this.videoTitle = entry.video.title;
        this.jobs = [];
    }
    compactTimestamp() {
        const { startsAt, endsAt } = this;
        return (0, date_fns_1.format)(startsAt, "HH:mm:ss.SSx - ") + (0, date_fns_1.format)(endsAt, "HH:mm:ss.SSx");
    }
    getFilename() {
        const asset = this.entry.video.media.assets.find((x) => x.type === "broadcastable").url;
        return config_1.CASPAR_PREFIX + asset;
    }
    loadbg = async () => {
        _1.log.info(`Loading video "${this.entry.video.title}"`);
        await _1.connection.loadbg(1, 50, this.getFilename());
    };
    stop = async (firedAt) => {
        _1.log.info(`Stopping video "${this.entry.video.title}"`);
        await _1.connection.stop(1, 50);
    };
    play = async (firedAt, seek = 0) => {
        _1.log.info(`Playing video "${this.entry.video.title}"`);
        await _1.connection.play(1, 50, this.getFilename(), undefined, undefined, undefined, undefined, undefined, seek ? seek * 50 : undefined);
    };
    async arm() {
        const { startsAt, endsAt, stop, play, loadbg, videoTitle } = this;
        const now = new Date();
        if (endsAt <= now) {
            _1.log.debug(`Not scheduling video (${endsAt} is in the past)`);
            return;
        }
        if (startsAt <= now) {
            _1.log.warn(`timer was armed while program should be active`);
            const requiredSeek = (0, date_fns_1.differenceInSeconds)(now, startsAt);
            _1.log.info(`playing immediately and seeking ${requiredSeek} seconds!`);
            this.play(new Date(), requiredSeek);
            this.jobs = [node_schedule_1.default.scheduleJob(endsAt, stop)];
        }
        else {
            _1.log.debug(`Arming timer for ${this.compactTimestamp()} "${videoTitle}"`);
            this.jobs = [
                node_schedule_1.default.scheduleJob((0, date_fns_1.sub)(startsAt, { seconds: 10 }), loadbg),
                node_schedule_1.default.scheduleJob(startsAt, play),
                node_schedule_1.default.scheduleJob(endsAt, stop),
            ];
        }
    }
    async disarm() {
        const { startsAt, endsAt, videoTitle } = this;
        _1.log.debug(`Disarming: Video "${videoTitle}" at ${this.compactTimestamp()}`);
        for (const job of this.jobs) {
            _1.log.debug(`Cancelling job ${job.name}`);
            job.cancel();
        }
    }
}
exports.ScheduledVideo = ScheduledVideo;
