/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NewOrganizationForm } from "../models/NewOrganizationForm.js";
import type { NewPlaylistForm } from "../models/NewPlaylistForm.js";
import type { NewVideoForm } from "../models/NewVideoForm.js";
import type { Organization } from "../models/Organization.js";
import type { Playlist } from "../models/Playlist.js";
import type { ResourceList } from "../models/ResourceList.js";
import type { User } from "../models/User.js";
import type { Video } from "../models/Video.js";
import type { CancelablePromise } from "../core/CancelablePromise.js";
import { request as __request } from "../core/request.js";

export class OrganizationService {
  /**
   * Get a list of organizations
   * @param offset Number of rows to skip
   * @param limit Number of rows to return
   * @param editor An id of the editor (user) to filter by
   * @returns any A list of organizations
   * @throws ApiError
   */
  public static getOrganization(
    offset?: number,
    limit: number = 5,
    editor?: number,
  ): CancelablePromise<
    ResourceList & {
      rows?: Array<Organization>;
    }
  > {
    return __request({
      method: "GET",
      path: `/organizations`,
      query: {
        offset: offset,
        limit: limit,
        editor: editor,
      },
    });
  }

  /**
   * Create a new organization
   * @param requestBody
   * @returns Organization Organization was created
   * @throws ApiError
   */
  public static postOrganization(
    requestBody: NewOrganizationForm,
  ): CancelablePromise<Organization> {
    return __request({
      method: "POST",
      path: `/organizations`,
      body: requestBody,
      mediaType: "application/json",
    });
  }

  /**
   * Get a specific organization by id
   * @param id
   * @returns Organization An organization
   * @throws ApiError
   */
  public static getOrganization1(id: number): CancelablePromise<Organization> {
    return __request({
      method: "GET",
      path: `/organizations/${id}`,
      errors: {
        404: `The requested resource was not found`,
      },
    });
  }

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
   * Create a new playlist for an organization
   * @param id
   * @param requestBody
   * @returns Playlist Playlist was created
   * @throws ApiError
   */
  public static postOrganization1(
    id: number,
    requestBody: NewPlaylistForm,
  ): CancelablePromise<Playlist> {
    return __request({
      method: "POST",
      path: `/organizations/${id}/playlists`,
      body: requestBody,
      mediaType: "application/json",
    });
  }

  /**
   * Get a list of members for an organization
   * @param id
   * @returns any A list of users
   * @throws ApiError
   */
  public static getOrganization2(id: number): CancelablePromise<
    ResourceList & {
      rows?: Array<User>;
    }
  > {
    return __request({
      method: "GET",
      path: `/organizations/${id}/members`,
      errors: {
        401: `Authentication is required for this request`,
        403: `You don't have the required permissions to perform this action`,
        404: `The requested resource was not found`,
      },
    });
  }

  /**
   * Add a user as a member to an organization
   * @param id
   * @param requestBody
   * @returns any The user was added as a member
   * @throws ApiError
   */
  public static postOrganization2(
    id: number,
    requestBody: {
      email: string;
    },
  ): CancelablePromise<any> {
    return __request({
      method: "POST",
      path: `/organizations/${id}/members`,
      body: requestBody,
      mediaType: "application/json",
      errors: {
        401: `Authentication is required for this request`,
        404: `The user with that email doesn't exist`,
      },
    });
  }

  /**
   * Remove a member from an organization
   * @param id
   * @param member
   * @returns any The member was removed from the organization
   * @throws ApiError
   */
  public static deleteOrganization(
    id: number,
    member: number,
  ): CancelablePromise<any> {
    return __request({
      method: "DELETE",
      path: `/organizations/${id}/members/${member}`,
    });
  }
}
