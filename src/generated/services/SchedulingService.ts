/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JukeboxSchedule } from "../models/JukeboxSchedule.js";
import type { ScheduleEntry } from "../models/ScheduleEntry.js";
import type { Video } from "../models/Video.js";
import type { CancelablePromise } from "../core/CancelablePromise.js";
import { request as __request } from "../core/request.js";

export class SchedulingService {
  /**
   * Get a portion of the schedule
   * @param from Defaults to start of day.
   * @param to Defaults to end of day of "from"
   * @returns ScheduleEntry A schedule
   * @throws ApiError
   */
  public static getSchedule(
    from?: string,
    to?: string,
  ): CancelablePromise<Array<ScheduleEntry>> {
    return __request({
      method: "GET",
      path: `/scheduling/entries`,
      query: {
        from: from,
        to: to,
      },
    });
  }

  /**
   * Internally get the pool of jukeboxable videos
   * @returns Video A list of videos
   * @throws ApiError
   */
  public static getScheduling(): CancelablePromise<Array<Video>> {
    return __request({
      method: "GET",
      path: `/scheduling/jukeboxable`,
    });
  }

  /**
   * Internally create jukebox schedule
   * @param requestBody
   * @returns any Jukebox schedule was created
   * @throws ApiError
   */
  public static postScheduling(
    requestBody: JukeboxSchedule,
  ): CancelablePromise<{
    message?: string;
  }> {
    return __request({
      method: "POST",
      path: `/scheduling/jukebox`,
      body: requestBody,
      mediaType: "application/json",
    });
  }
}
