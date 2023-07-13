/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NewVideoForm } from "../models/NewVideoForm.js";
import type { ResourceList } from "../models/ResourceList.js";
import type { Video } from "../models/Video.js";
import type { CancelablePromise } from "../core/CancelablePromise.js";
import { request as __request } from "../core/request.js";

export class VideoService {
  /**
   * Create a new video for an organization
   * @param orgId
   * @param requestBody
   * @returns Video Video was created
   * @throws ApiError
   */
  public static newVideo(
    orgId: number,
    requestBody: NewVideoForm,
  ): CancelablePromise<Video> {
    return __request({
      method: "POST",
      path: `/organizations/${orgId}/videos`,
      body: requestBody,
      mediaType: "application/json",
    });
  }

  /**
   * Get a list of videos
   * @param offset Number of rows to skip
   * @param limit Number of rows to return
   * @param inPlaylist An id of a playlist to filter by. Orders by playlist entry indices.
   * @param organization An id of an organization to filter by
   * @returns any A list of videos
   * @throws ApiError
   */
  public static getVideo(
    offset?: number,
    limit: number = 5,
    inPlaylist?: number,
    organization?: number,
  ): CancelablePromise<
    ResourceList & {
      rows?: Array<Video>;
    }
  > {
    return __request({
      method: "GET",
      path: `/videos`,
      query: {
        offset: offset,
        limit: limit,
        inPlaylist: inPlaylist,
        organization: organization,
      },
    });
  }

  /**
   * Get a specific video by id
   * @param id
   * @returns Video A video
   * @throws ApiError
   */
  public static getVideo1(id: number): CancelablePromise<Video> {
    return __request({
      method: "GET",
      path: `/videos/${id}`,
      errors: {
        404: `The requested resource was not found`,
      },
    });
  }
}