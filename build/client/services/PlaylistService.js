"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PlaylistService = void 0;
const request_1 = require("../core/request");
class PlaylistService {
    /**
     * Create a new playlist for an organization
     * @param id
     * @param requestBody
     * @returns Playlist Playlist was created
     * @throws ApiError
     */
    static postPlaylist(id, requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/organizations/${id}/playlists`,
            body: requestBody,
            mediaType: 'application/json',
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
    static getPlaylist(offset, limit = 5, organization) {
        return (0, request_1.request)({
            method: 'GET',
            path: `/playlists`,
            query: {
                'offset': offset,
                'limit': limit,
                'organization': organization,
            },
        });
    }
    /**
     * Get a specific playlist by id
     * @param id
     * @returns Playlist An playlist
     * @throws ApiError
     */
    static getPlaylist1(id) {
        return (0, request_1.request)({
            method: 'GET',
            path: `/playlists/${id}`,
            errors: {
                404: `The requested resource was not found`,
            },
        });
    }
}
exports.PlaylistService = PlaylistService;
