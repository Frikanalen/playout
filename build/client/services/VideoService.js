"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.VideoService = void 0;
const request_1 = require("../core/request");
class VideoService {
    /**
     * Create a new video for an organization
     * @param orgId
     * @param requestBody
     * @returns Video Video was created
     * @throws ApiError
     */
    static newVideo(orgId, requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/organizations/${orgId}/videos`,
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Get a list of videos
     * @param offset Number of rows to skip
     * @param limit Number of rows to return
     * @param inPlaylist An id of a playlist to filter by. Orders by playlist entry indices.
     * @returns any A list of videos
     * @throws ApiError
     */
    static getVideo(offset, limit = 5, inPlaylist) {
        return (0, request_1.request)({
            method: 'GET',
            path: `/videos`,
            query: {
                'offset': offset,
                'limit': limit,
                'inPlaylist': inPlaylist,
            },
        });
    }
    /**
     * Get a specific video by id
     * @param id
     * @returns Video A video
     * @throws ApiError
     */
    static getVideo1(id) {
        return (0, request_1.request)({
            method: 'GET',
            path: `/videos/${id}`,
            errors: {
                404: `The requested resource was not found`,
            },
        });
    }
    /**
     * Internally create a video media entry
     * @param requestBody
     * @returns any Video media was created
     * @throws ApiError
     */
    static postVideo(requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/videos/media`,
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Internally create a video media asset entry
     * @param id
     * @param requestBody
     * @returns any Video media asset was created
     * @throws ApiError
     */
    static postVideo1(id, requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/videos/media/${id}/assets`,
            body: requestBody,
            mediaType: 'application/json',
        });
    }
}
exports.VideoService = VideoService;
