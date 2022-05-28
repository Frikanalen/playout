"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SchedulingService = void 0;
const request_1 = require("../core/request");
class SchedulingService {
    /**
     * Get a portion of the schedule
     * @param from Defaults to start of day.
     * @param to Defaults to end of day of "from"
     * @returns ScheduleEntry A schedule
     * @throws ApiError
     */
    static getSchedule(from, to) {
        return (0, request_1.request)({
            method: 'GET',
            path: `/scheduling/entries`,
            query: {
                'from': from,
                'to': to,
            },
        });
    }
    /**
     * Internally get the pool of jukeboxable videos
     * @returns Video A list of videos
     * @throws ApiError
     */
    static getScheduling() {
        return (0, request_1.request)({
            method: 'GET',
            path: `/scheduling/jukeboxable`,
        });
    }
    /**
     * Internally create jukebox schedule
     * @param requestBody
     * @returns any Jukebox schedule was created
     * @throws ApiError
     */
    static postScheduling(requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/scheduling/jukebox`,
            body: requestBody,
            mediaType: 'application/json',
        });
    }
}
exports.SchedulingService = SchedulingService;
