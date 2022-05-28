"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuthenticationService = void 0;
const request_1 = require("../core/request");
class AuthenticationService {
    /**
     * Register a new user
     * With a successful response, you will be logged in with the new user and assigned a new CSRF token.
     * @param requestBody
     * @returns any The user was created
     * @throws ApiError
     */
    static postAuthentication(requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/auth/register`,
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                409: `Email is already in use`,
            },
        });
    }
    /**
     * Log in with existing user
     * With a successful response, you will be logged in with the specified user and assigned a new CSRF token.
     * @param requestBody
     * @returns any Login was successful
     * @throws ApiError
     */
    static loginUser(requestBody) {
        return (0, request_1.request)({
            method: 'POST',
            path: `/auth/login`,
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                401: `Incorrect username or password`,
            },
        });
    }
    /**
     * Log out of the currently logged in user (if any)
     * @returns any Logout was successful
     * @throws ApiError
     */
    static postAuthentication1() {
        return (0, request_1.request)({
            method: 'POST',
            path: `/auth/logout`,
        });
    }
    /**
     * Get information about the logged in user
     * Returns the logged in user (omitted if anonymous). If the `hasPermission` query param is used, only a status code and message is returned instead.
     * @returns any Successful request or permission granted
     * @throws ApiError
     */
    static userProfile() {
        return (0, request_1.request)({
            method: 'GET',
            path: `/auth/user`,
            errors: {
                400: `Specified permission doesn't exist`,
                401: `Authentication required or permission denied (only for \`hasPermission\`)`,
            },
        });
    }
}
exports.AuthenticationService = AuthenticationService;
