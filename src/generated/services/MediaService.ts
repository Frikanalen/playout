/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { VideoMediaAssetForm } from "../models/VideoMediaAssetForm.js";
import type { VideoMediaForm } from "../models/VideoMediaForm.js";
import type { CancelablePromise } from "../core/CancelablePromise.js";
import { request as __request } from "../core/request.js";

export class MediaService {
  /**
   * (Used by media-processor) Register an uploaded file in the database
   * @param xApiKey
   * @param requestBody
   * @returns any Video media was created
   * @throws ApiError
   */
  public static postMedia(
    xApiKey: string,
    requestBody: VideoMediaForm,
  ): CancelablePromise<{
    id: number;
  }> {
    return __request({
      method: "POST",
      path: `/videos/media`,
      headers: {
        "X-Api-Key": xApiKey,
      },
      body: requestBody,
      mediaType: "application/json",
    });
  }

  /**
   * (Used by media-processor) Register a new video media asset
   * @param id
   * @param xApiKey
   * @param requestBody
   * @returns any Video media asset was created
   * @throws ApiError
   */
  public static postMedia1(
    id: number,
    xApiKey: string,
    requestBody: VideoMediaAssetForm,
  ): CancelablePromise<{
    id: number;
  }> {
    return __request({
      method: "POST",
      path: `/videos/media/${id}/assets`,
      headers: {
        "X-Api-Key": xApiKey,
      },
      body: requestBody,
      mediaType: "application/json",
    });
  }
}
