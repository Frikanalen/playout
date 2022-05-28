"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OrganizationService = void 0;
const request_1 = require("../core/request");
class OrganizationService {
    /**
     * Get a list of organizations
     * @param offset Number of rows to skip
     * @param limit Number of rows to return
     * @param editor An id of the editor (user) to filter by
     * @returns any A list of organizations
     * @throws ApiError
     */
    static getOrganization(offset, limit = 5, editor) {
        return (0, request_1.request)({
            method: 'GET',
            path: `/organizations`,
            query: {
                'offset': offset,
                'limit': limit,
                'editor': editor,
            },
        });
    }
    /**
     * Create a new organization
     * @param requestBody
     * @returns Organization Organization was created
     * @throws ApiError
     */
    static postOrganization(requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/organizations`,
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Get a specific organization by id
     * @param id
     * @returns Organization An organization
     * @throws ApiError
     */
    static getOrganization1(id) {
        return (0, request_1.request)({
            method: 'GET',
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
    static newVideo(orgId, requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/organizations/${orgId}/videos`,
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Create a new playlist for an organization
     * @param id
     * @param requestBody
     * @returns Playlist Playlist was created
     * @throws ApiError
     */
    static postOrganization1(id, requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/organizations/${id}/playlists`,
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Get a list of members for an organization
     * @param id
     * @returns any A list of users
     * @throws ApiError
     */
    static getOrganization2(id) {
        return (0, request_1.request)({
            method: 'GET',
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
    static postOrganization2(id, requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/organizations/${id}/members`,
            body: requestBody,
            mediaType: 'application/json',
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
    static deleteOrganization(id, member) {
        return (0, request_1.request)({
            method: 'DELETE',
            path: `/organizations/${id}/members/${member}`,
        });
    }
}
exports.OrganizationService = OrganizationService;
