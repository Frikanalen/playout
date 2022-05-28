"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppService = void 0;
const request_1 = require("../core/request");
class AppService {
    /**
     * Get OpenAPI specification
     * @returns any The specification, in JSON format.
     * @throws ApiError
     */
    static getApp() {
        return (0, request_1.request)({
            method: 'GET',
            path: `/open-api-spec.json`,
        });
    }
    /**
     * Get core data and config
     * This endpoint returns such things as server hostnames, categories, and other mostly static data.
     * @returns Config The config result
     * @throws ApiError
     */
    static getApp1() {
        return (0, request_1.request)({
            method: 'GET',
            path: `/config`,
        });
    }
}
exports.AppService = AppService;
