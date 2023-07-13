/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Bulletin } from "../models/Bulletin.js";
import type { NewBulletinForm } from "../models/NewBulletinForm.js";
import type { ResourceList } from "../models/ResourceList.js";
import type { CancelablePromise } from "../core/CancelablePromise.js";
import { request as __request } from "../core/request.js";

export class BulletinsService {
  /**
   * Get a list of bulletins
   * @returns any A list of bulletins
   * @throws ApiError
   */
  public static getBulletins(): CancelablePromise<
    ResourceList & {
      rows?: Array<Bulletin>;
    }
  > {
    return __request({
      method: "GET",
      path: `/bulletins`,
    });
  }

  /**
   * Create a new bulletin
   * @param requestBody
   * @returns Bulletin Organization was created
   * @throws ApiError
   */
  public static postBulletins(
    requestBody: NewBulletinForm,
  ): CancelablePromise<Bulletin> {
    return __request({
      method: "POST",
      path: `/bulletins`,
      body: requestBody,
      mediaType: "application/json",
    });
  }

  /**
   * Get a specific news bulletin by id
   * @param id
   * @returns Bulletin Bulletin
   * @throws ApiError
   */
  public static getBulletins1(id: number): CancelablePromise<Bulletin> {
    return __request({
      method: "GET",
      path: `/bulletins/${id}`,
      errors: {
        404: `The requested resource was not found`,
      },
    });
  }

  /**
   * Update a bulletin
   * @param id
   * @returns Bulletin Bulletin
   * @throws ApiError
   */
  public static putBulletins(id: number): CancelablePromise<Bulletin> {
    return __request({
      method: "PUT",
      path: `/bulletins/${id}`,
      errors: {
        403: `You don't have the required permissions to perform this action`,
        404: `The requested resource was not found`,
      },
    });
  }

  /**
   * Deletes a bulletin
   * @param id
   * @returns void
   * @throws ApiError
   */
  public static deleteBulletins(id: number): CancelablePromise<void> {
    return __request({
      method: "DELETE",
      path: `/bulletins/${id}`,
      errors: {
        403: `You don't have the required permissions to perform this action`,
        404: `The requested resource was not found`,
      },
    });
  }
}
