"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ServiceService = void 0;
const request_1 = require("../core/request");
class ServiceService {
    /**
     * @param hasPermission Check if the logged in user has a specific role permission. Should be the name of a permission (e.g. `ATEM_CONTROL`)
     * @returns any Successful request or permission granted
     * @throws ApiError
     */
    static checkPermission(hasPermission) {
        return (0, request_1.request)({
            method: 'GET',
            path: `/auth/hasPermission`,
            query: {
                'hasPermission': hasPermission,
            },
        });
    }
}
exports.ServiceService = ServiceService;
