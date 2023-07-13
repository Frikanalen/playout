/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NewPlaylistForm } from "../models/NewPlaylistForm.js";
import type { Playlist } from "../models/Playlist.js";
import type { ResourceList } from "../models/ResourceList.js";
import type { CancelablePromise } from "../core/CancelablePromise.js";
import { request as __request } from "../core/request.js";

export class PlaylistService {
  /**
   * Create a new playlist for an organization
   * @param id
   * @param requestBody
   * @returns Playlist Playlist was created
   * @throws ApiError
   */
  public static postPlaylist(
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
   * Get a list of playlists
   * @param offset Number of rows to skip
   * @param limit Number of rows to return
   * @param organization An id of the organization to filter by
   * @returns any A list of playlists
   * @throws ApiError
   */
  public static getPlaylist(
    offset?: number,
    limit: number = 5,
    organization?: number,
  ): CancelablePromise<
    ResourceList & {
      rows?: Array<Playlist>;
    }
  > {
    return __request({
      method: "GET",
      path: `/playlists`,
      query: {
        offset: offset,
        limit: limit,
        organization: organization,
      },
    });
  }

  /**
   * Get a specific playlist by id
   * @param id
   * @returns Playlist An playlist
   * @throws ApiError
   */
  public static getPlaylist1(id: number): CancelablePromise<Playlist> {
    return __request({
      method: "GET",
      path: `/playlists/${id}`,
      errors: {
        404: `The requested resource was not found`,
      },
    });
  }
}
